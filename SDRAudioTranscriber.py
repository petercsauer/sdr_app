import numpy as np
from scipy.signal import resample_poly, firwin, lfilter
import pyaudio
from rtlsdr import RtlSdr
import threading
import queue
import whisper
import tempfile
import openai
import socket
from concurrent.futures import ThreadPoolExecutor
import traceback
import requests
from datetime import datetime
import os
import wave
import json  # Import JSON module for serialization



class SDRAudioTranscriber:
    def __init__(self, center_freq = 162400000, duration = 20, audio = False, aws = False, language = "English"):
        self.aws = aws
        self.sdr = RtlSdr()
        self._setup_sdr(center_freq)
        self.p = pyaudio.PyAudio()
        self.stream = self._setup_pyaudio_stream()
        self.process_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.duration = duration
        self.client = openai.OpenAI(api_key = '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')
        self.latest_transcription = None
        self.transcriptions = []
        self.translations = []
        self.summary = ""
        self.audio = audio
        self.file_id = 0  # Initialize the counter for file IDs
        self.transcription_lock = threading.Lock()
        self.sdr_thread = threading.Thread(target=self._sdr_read_thread)
        self.sdr_thread.start()
        self.executor = ThreadPoolExecutor(max_workers=10)  # Adjust the number of workers as needed
        self.search_phrase = "The following is a transcription of a NOAA weather forecast on 162.4 MHz. Please summarize it in a verbose yet concise manner."
        self.language = language
        self.udp_ip = "127.0.0.1"
        self.udp_port = 5005  # Assuming 5005 for incoming settings; make sure it doesn't conflict
        self.settings_listener_thread = threading.Thread(target=self._udp_settings_listener)
        self.settings_listener_thread.daemon = True  # Daemonize thread
        #self.search_phrase = "This is a transcription of a NOAA weather forecast. Please give a summary of the local temperatures as a bulleted list with enters as a \n character"

    def _udp_settings_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.udp_ip, self.udp_port))
        print(f"Listening for settings on UDP {self.udp_port}")

        while True:
            data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
            print(f"Received message: {data} from {addr}")

            try:
                settings = json.loads(data)
                # Example settings: {"language": "Spanish", "duration": 10, "center_freq": 162400000, "search_phrase": "Please summarize this in Spanish."}
                if 'language' in settings:
                    self.set_language(settings['language'])
                    print("set language")

                if 'duration' in settings:
                    self.duration = int(settings['duration'])
                    print("set duration")

                if 'center_freq' in settings:
                    self.change_center_frequency(int(settings['center_freq']))
                    print("set freq")
                if 'search_phrase' in settings:
                    self.set_search(settings['search_phrase'])
                    print("set search")

            except Exception as e:
                print(f"Failed to parse settings: {e}")

    def set_language(self, language):
        self.language = language
    
    def set_search(self, search_phrase):
        self.search_phrase = search_phrase

    def get_latest_data(self):
        return {
            "transcriptions": self.transcriptions,
            "translations": self.translations,
            "summary": self.summary,
            "timestamps": ["2024-04-10T12:00:00"]
        }

    def change_center_frequency(self, center_freq):
        self.sdr.center_freq = center_freq

    def _broadcast_json_data(self):
        data = {
            "transcriptions": self.transcriptions,
            "translations": self.translations,
            "summary": [self.summary],  # Making summary a list to keep the structure consistent
            "timestamps": [datetime.now().isoformat()]  # Current timestamp; adjust format as needed
        }
        self._send_udp(json.dumps(data))  # Convert dictionary to JSON string and send via UDP

    def _setup_sdr(self, center_freq):
        self.sdr.sample_rate = 2048000  # 2.048 MHz
        self.sdr.center_freq = center_freq
        self.sdr.gain = 20

    def _setup_pyaudio_stream(self):
        return self.p.open(format=pyaudio.paFloat32,
                           channels=1,
                           rate=48000,
                           output=True)
    

    def _sdr_read_thread(self):
        while True:
            try:
                # Attempt to read samples
                samples = self.sdr.read_samples(self.sdr.sample_rate * self.duration)
                self.process_queue.put(samples)
            except ZeroDivisionError:
                print("Detected ZeroDivisionError, possibly due to a zero sample rate. Attempting to reset SDR connection.")
                self._reset_sdr_connection()
            except Exception as e:
                print(f"An error occurred: {e}")

    def _reset_sdr_connection(self):
        # Attempt to close the current SDR connection gracefully
        try:
            self.sdr.close()
        except Exception as e:
            print(f"Error while closing SDR: {e}")
        
        # Reinitialize the SDR
        try:
            self.sdr = RtlSdr()
            self._setup_sdr(self.sdr.center_freq)
            print("SDR connection has been reset.")
        except Exception as e:
            print(f"Error reinitializing SDR: {e}")


    def _process_samples(self, samples):
        sdr_samp_rate = 2048000
        samp_rate = 48000

        resampled_signal = resample_poly(samples, 1, int(sdr_samp_rate/samp_rate))
        lpf_coeffs = firwin(numtaps=101, cutoff=12500, width=1000, fs=samp_rate, window='hamming')
        filtered_signal = lfilter(lpf_coeffs, 1.0, resampled_signal)
        demodulated_signal = self._demodulate_quad(filtered_signal, demod_gain=samp_rate/(2*np.pi*6000))
        de_emphasized_signal = self._de_emphasis_filter(demodulated_signal, fs=samp_rate)
        self.output_queue.put(de_emphasized_signal.astype(np.float32).tobytes())

    def _demodulate_quad(self, fm_signal, demod_gain):
        return np.angle(fm_signal[1:] * np.conj(fm_signal[:-1])) * demod_gain

    def _de_emphasis_filter(self, signal, fs):
        tau = 75e-6  # 75 microseconds
        fc = 1 / (2 * np.pi * tau)
        alpha = 1 / (1 + (fs / (2 * np.pi * fc)))
        b = [1 - alpha]
        a = [1, -alpha]
        return lfilter(b, a, signal)
    # Function to translate text using OpenAI
    def _translate_text(self, text):
        response = self.client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": f"Please translate the following text to {self.language} and only return the translated text, nothing else: {text}"}
        ]
        )
        return response.choices[0].message.content

    def _openai_whisper_transcribe(self, audio_signal):
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            wf = wave.open(temp_file.name, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paFloat32))
            wf.setframerate(48000)
            wf.writeframes(audio_signal)
            wf.close()

            with open(temp_file.name, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
                self.latest_transcription = transcript.text
                
                translation_response = self._translate_text(self.latest_transcription)

            
            self.latest_transcription = transcript.text
            #self._send_udp("t:"+str(self.file_id)+":"+self.latest_transcription)
            print("Transcription:")
            print(transcript.text)
            print("Translation:")
            print(translation_response)
            self._broadcast_json_data()

            self.transcriptions.append(transcript.text)
            self.translations.append(translation_response)
            self.summary = self._summarize_transcriptions(transcript.text)

    def _summarize_transcriptions(self, transcript, length=10):
        all_transcriptions = ''.join(self.transcriptions[max(len(self.transcriptions),0)-length:])
        response = self.client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": self.search_phrase},
            {"role": "user", "content": all_transcriptions}
        ]
        )
        summary = response.choices[0].message.content
        print("Summary:")
        print(summary)
        self._broadcast_json_data()
        return summary
    
    def _save_audio_to_wav(self, audio_signal):
        # Get current date and time
        now = datetime.now()

        # Format the date and time as a string in the format you prefer, e.g., YYYY-MM-DD_HH-MM-SS
        # This format avoids using characters that are invalid in filenames, like slashes or colons.
        date_time_str = now.strftime("%Y-%m-%d_%H-%M-%S")

        # Incorporate the date and time string into your filename
        filename = f"{date_time_str}.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paFloat32))
            wf.setframerate(48000)  # Assuming a sample rate of 48kHz
            wf.writeframes(audio_signal)
            url = 'http://44.212.137.130:5000/upload'
            files = {'file': open(filename, 'rb')}

            # To delete the file
            try:
                response = requests.post(url, files=files)
                print(response.text)
                os.remove(filename)
                print(f"Successfully deleted the file: {filename}")
            except OSError as e:
                print(f"Error: {e.strerror} - {e.filename}")


        

    def _send_udp(self, data, is_audio=False):
        udp_ip = "127.0.0.1"  # IP of the UDP server, change if different
        udp_port = 5006  # Port of the UDP server

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP socket

        if is_audio:
            # For audio data, the data parameter is expected to be a byte array
            sock.sendto(data, (udp_ip, udp_port))
        else:
            # For text, encode the string to bytes
            sock.sendto(data.encode(), (udp_ip, udp_port))


    def get_latest_transcription(self):
        with self.transcription_lock:
            return self.latest_transcription

    def run(self):
        # Start listening for settings before entering the main loop
        self.settings_listener_thread.start()
        try:
            while True:
                if not self.process_queue.empty():
                    samples = self.process_queue.get()
                    self.executor.submit(self._process_samples, samples)

                if not self.output_queue.empty():
                    audio_signal = self.output_queue.get()
                    # Consider moving the following tasks to a separate method or thread if they're time-consuming
                    if(self.aws):
                        self._save_audio_to_wav(audio_signal)
                    self._openai_whisper_transcribe(audio_signal)
                    if self.audio:
                        self.stream.write(audio_signal)
                    self.file_id += 1
                    self._broadcast_json_data()  # Broadcast the JSON data over UDP


        except KeyboardInterrupt:
            print("Interrupt received, stopping...")
        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()  # This will print the stack trace
        finally:
            self._cleanup()

    def _cleanup(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.executor.shutdown(wait=True)
        self.sdr.close()

# Usage:
# transcriber = SDRAudioTranscriber
