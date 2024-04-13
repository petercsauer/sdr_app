const dgram = require('dgram');
const client = dgram.createSocket('udp4');
const { ipcRenderer } = require('electron');

let showSpinnerTimeout = null;

ipcRenderer.on('python-exit', (event, message) => {
    const spinner = document.getElementById('loadingSpinner');
    const errorContainer = document.createElement('div');
    errorContainer.innerHTML = `
        <span class="navbar-text text-danger">
            ${message}
        </span>
        <span class="navbar-text text-danger">
            <i class="fas fa-times-circle"></i>
        </span>
    `;

    // Replace the spinner with the error message and icon
    spinner.replaceWith(errorContainer);
});

ipcRenderer.on('udp-message', (event, message) => {
    const spinner = document.getElementById('loadingSpinner');
    // Hide the spinner immediately when a message is received
    spinner.classList.add('d-none');

    // Clear any existing timeout to potentially show the spinner
    if (showSpinnerTimeout) clearTimeout(showSpinnerTimeout);

    // Set a new timeout to show the spinner 1 second after the message is received,
    // if no new messages arrive in that 1 second period
    showSpinnerTimeout = setTimeout(() => {
        spinner.classList.remove('d-none'); // Show spinner
    }, 1000); // 1 second delay before showing the spinner

    // Proceed to handle the message (e.g., display a card, update the summary, etc.
    const data = JSON.parse(message);
    if (data.transcriptions && data.transcriptions.length > 0) {
        displayTranscriptions(data.transcriptions, data.translations);

    }
    if (data.summary) {
        updateSummary(data.summary); // Update the summary if present
    }
});

// In renderer.js or similar
require('electron').ipcRenderer.on('test-channel', (event, message) => {
    console.log(message); // Should log "Hello from main process"
});

function displayTranscriptions(transcriptions, translations) {
    const transcriptionsContainer = document.getElementById('transcriptions-container');
    
    // Clear existing translations
    transcriptionsContainer.innerHTML = '';

    // Reverse the translations array so the last item appears first
    for (let i = 0; i < transcriptions.length; i++) {
        createTranscriptionCard(transcriptions[i], translations[i], transcriptionsContainer);
    }
}

function createTranscriptionCard(transcription, translation, container) {
    // Create card element for each translation
    const cardEl = document.createElement('div');
    cardEl.className = 'card mb-3';
    cardEl.innerHTML = `
        <div class="card-body" title = "${translation}">
            <p class="card-text">${transcription}</p>
        </div>
    `;
    cardEl.setAttribute('data-tooltip', transcription); // Set translation as tooltip
    // Prepend the new card to the container to ensure the last item appears first
    container.prepend(cardEl);
}

function updateSummary(summary) {
    const summaryDiv = document.getElementById('summary');
    summaryDiv.textContent = summary; // Update summary text
}



const channelFrequencies = {
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
};

window.onload = () => {
    const centerFreqSelect = document.getElementById('center_freq');
    Object.keys(channelFrequencies).forEach(key => {
        const option = document.createElement('option');
        option.value = channelFrequencies[key].rx;
        option.text = key + ' - ' + channelFrequencies[key].label;
        centerFreqSelect.appendChild(option);
    });
};

document.getElementById('settings-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const language = document.getElementById('language').value;
    const duration = document.getElementById('duration').value;
    const center_freq = document.getElementById('center_freq').value;
    const search_phrase = document.getElementById('search_phrase').value;

    const settings = {};
    if (language) settings.language = language;
    if (duration) settings.duration = duration;
    if (center_freq) settings.center_freq = center_freq;
    if (search_phrase) settings.search_phrase = search_phrase;

    client.send(JSON.stringify(settings), 5005, 'localhost', (err) => {
        if (err) console.log(err);
        console.log('Settings sent:', settings);
    });
});
