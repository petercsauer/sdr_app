from SDRAudioTranscriber import SDRAudioTranscriber

def main():
    # Initialize the transcriber with a specific center frequency
    center_freq = 162400000  # Example frequency

    channel_frequencies = {
    '1001': {'rx': 156050000.0, 'label': 'Port Operations and Commercial, VTS. Available only in New Orleans / Lower Mississippi area.'},
    '1005': {'rx': 156250000.0, 'label': 'Port Operations or VTS in the Houston, New Orleans and Seattle areas.'},
    '06': {'rx': 156300000.0, 'label': 'Intership Safety'},
    '1007': {'rx': 156350000.0, 'label': 'Commercial. VDSMS'},
    '86': {'rx': 161925000.0, 'label': 'Public Correspondence (Marine Operator). VDSMS'},
    '87': {'rx': 157375000.0, 'label': 'Public Correspondence (Marine Operator). VDSMS'},
    '88': {'rx': 157425000.0, 'label': 'Commercial, Intership only. VDSMS'},
    '13': {'rx': 156650000.0, 'label': 'Intership Navigation Safety (Bridge-to-bridge). Ships >20m length maintain a listening watch on this channel in US waters.'},
    '16': {'rx': 156800000.0, 'label': 'International Distress, Safety and Calling. Ships required to carry radio, USCG, and most coast stations maintain a listening watch on this channel.'},
    'NOAA': {'rx': 162400000.0, 'label': 'NOAA Weather reports'},
    '100.7': {'rx': 100700000.0, 'label': 'NOAA Weather reports'}
    }

    
    transcriber = SDRAudioTranscriber(channel_frequencies['NOAA']['rx'], 10, True)

    # Run the transcriber
    transcriber.run()

if __name__ == "__main__":
    main()