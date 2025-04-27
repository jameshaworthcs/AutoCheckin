document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    const accountForm = document.getElementById('account-form');
    const emailInput = document.getElementById('email');
    const tokenInput = document.getElementById('token');
    const codesSuffixInput = document.getElementById('codes_suffix');
    const checkoutApiUrlDisplay = document.getElementById('checkout-api-url-display');
    const fullCodesUrlDisplay = document.getElementById('full-codes-url');
    const previewLink = document.getElementById('preview-link');
    const configWarningPlaceholder = document.getElementById('config-warning-placeholder');
    // Status display elements
    const lastSessionRefreshDisplay = document.getElementById('last-session-refresh');
    const lastCodeAttemptDisplay = document.getElementById('last-code-attempt');
    const untriedCodesCountDisplay = document.getElementById('untried-codes-count');

    let checkoutApiUrlBase = '';
    let isUserConfigured = false;

    // --- Navigation --- 
    function setActiveSection(sectionId) {
        if (!isUserConfigured && sectionId !== 'account') {
            console.warn('Access denied: Please configure account first.');
            showConfigurationWarning();
            return;
        }

        contentSections.forEach(section => {
            section.classList.toggle('active', section.id === sectionId);
        });
        navLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.section === sectionId);
        });
        window.location.hash = sectionId;
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            if (link.classList.contains('disabled')) {
                showConfigurationWarning();
                return;
            }
            const sectionId = link.dataset.section;
            setActiveSection(sectionId);
        });
    });

    // --- Configuration Warning & Navigation State ---
    function showConfigurationWarning() {
        if (!configWarningPlaceholder) return;
        configWarningPlaceholder.innerHTML = `
            <div class="config-warning">
                <strong>Configuration Incomplete:</strong> Please enter and save your Email Address and Checkin Token to enable other features.
            </div>
        `;
        configWarningPlaceholder.style.display = 'block';
    }

    function hideConfigurationWarning() {
        const warningDiv = configWarningPlaceholder.querySelector('.config-warning');
        if (warningDiv) {
             configWarningPlaceholder.innerHTML = '';
             configWarningPlaceholder.style.display = 'none';
        }
    }
    
    function showTemporarySuccessMessage(message) {
        if (!configWarningPlaceholder) return;
        configWarningPlaceholder.innerHTML = `
            <div class="config-success">
                <strong>Success:</strong> ${message}
            </div>
        `;
        configWarningPlaceholder.style.display = 'block';
        setTimeout(() => {
            const successDiv = configWarningPlaceholder.querySelector('.config-success');
             if (successDiv) {
                 configWarningPlaceholder.innerHTML = '';
                 configWarningPlaceholder.style.display = 'none';
             }
        }, 5000);
    }

    function updateNavigationState() {
        navLinks.forEach(link => {
            const sectionId = link.dataset.section;
            if (sectionId !== 'account') {
                link.classList.toggle('disabled', !isUserConfigured);
                if (!isUserConfigured) {
                    link.setAttribute('aria-disabled', 'true');
                } else {
                    link.removeAttribute('aria-disabled');
                }
            }
        });
    }

    // --- Initialization --- 
    async function initializeApp() {
        let configLoaded = false;
        try {
            const response = await fetch('/api/v1/local/config');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const config = await response.json();

            if (config.success && config.data) {
                configLoaded = true;
                checkoutApiUrlBase = config.data.checkout_api_url || '';
                const user = config.data.user || {};
                const state = config.data.state || {};
                const logs = config.data.logs || []; // Get logs

                // Populate form
                checkoutApiUrlDisplay.textContent = checkoutApiUrlBase ? `${checkoutApiUrlBase}/` : '[Set LOCAL_CHECKOUT_API_URL in .env]/';
                emailInput.value = user.email || '';
                tokenInput.value = user.token || '';
                codesSuffixInput.value = user.codes_url_suffix || 'api/app/active/yrk/cs/2';

                // Populate status section
                lastSessionRefreshDisplay.textContent = formatTimestamp(state.last_session_refresh);
                lastCodeAttemptDisplay.textContent = formatTimestamp(state.last_code_attempt);
                untriedCodesCountDisplay.textContent = state.available_untried_codes_count !== undefined 
                                                     ? state.available_untried_codes_count 
                                                     : 'N/A';
                // You might need to add/update the tried_codes_count display element here too if you haven't already
                // const triedCountEl = document.getElementById('tried-codes-count');
                // if (triedCountEl) triedCountEl.textContent = state.tried_codes_count !== undefined ? state.tried_codes_count : 'N/A';

                // ** Call updateLogs with the fetched logs **
                updateLogs(logs); 

                // ** Check configuration status AFTER fetching **
                isUserConfigured = !!(user.email && user.token);

                updateCodesUrlPreview();
            } else {
                console.error('Failed to load config:', config.message || 'Unknown error');
                checkoutApiUrlDisplay.textContent = '[Error loading config]/';
                isUserConfigured = false;
            }

        } catch (error) {
            console.error('Error fetching config:', error);
            checkoutApiUrlDisplay.textContent = '[Error loading config]/';
            isUserConfigured = false;
        } finally {
             // ** Update UI state AFTER fetch attempt (success or fail) **
             updateNavigationState();

            // Show warning OR check for save confirmation
            if (!isUserConfigured) {
                showConfigurationWarning();
            } else {
                hideConfigurationWarning();
                // Check for save confirmation param only if configured
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.has('saved') && urlParams.get('saved') === 'true') {
                    showTemporarySuccessMessage('Configuration saved successfully!');
                    // Clean the URL
                    history.replaceState(null, '', window.location.pathname + window.location.hash);
                }
            }

            // Handle initial section AFTER determining configuration status
            let initialSection = 'account'; // Default to account
            if (isUserConfigured) {
                const hashSection = window.location.hash.substring(1);
                const validSections = Array.from(contentSections).map(s => s.id);
                if (validSections.includes(hashSection)) {
                    initialSection = hashSection;
                }
            } 
            // Make sure the active section is set correctly, respecting the config status check
            setActiveSection(initialSection);
             // If not configured, setActiveSection will force 'account' anyway
        }
    }

    // --- Utility Functions ---
    function formatTimestamp(isoTimestamp) {
        if (!isoTimestamp) {
            return 'N/A';
        }
        try {
            const date = new Date(isoTimestamp);
            // Basic formatting, adjust as needed
            return date.toLocaleString(); 
        } catch (e) {
            console.error("Error formatting timestamp:", e);
            return 'Invalid Date';
        }
    }

    // --- Account Form Logic --- 
    function updateCodesUrlPreview() {
        if (!checkoutApiUrlBase) {
             fullCodesUrlDisplay.textContent = 'N/A (Set LOCAL_CHECKOUT_API_URL)';
             previewLink.href = '#';
             previewLink.style.display = 'none';
             return;
        }

        let suffix = codesSuffixInput.value.trim();
        let fullUrl = '';

        // Ensure correct joining slash
        const baseEndsWithSlash = checkoutApiUrlBase.endsWith('/');
        const suffixStartsWithSlash = suffix.startsWith('/');

        if (baseEndsWithSlash && suffixStartsWithSlash) {
            suffix = suffix.substring(1);
        } else if (!baseEndsWithSlash && !suffixStartsWithSlash && suffix) {
            suffix = '/' + suffix;
        }
        
        fullUrl = checkoutApiUrlBase + suffix;

        fullCodesUrlDisplay.textContent = fullUrl;
        previewLink.href = fullUrl;
        previewLink.style.display = 'inline'; // Show preview link
    }

    codesSuffixInput.addEventListener('input', updateCodesUrlPreview);

    // Initial call to setup the page
    initializeApp();

    // --- Placeholder for other sections (Submit, Logs, Timetable) ---
    const manualSubmitBtn = document.getElementById('manual-submit-btn');
    const submitStatus = document.getElementById('submit-status');

    if (manualSubmitBtn) {
        manualSubmitBtn.addEventListener('click', async () => {
            if (!isUserConfigured) { // Prevent action if not configured
                 submitStatus.textContent = 'Error: Please configure account first.';
                 showConfigurationWarning(); // Make sure warning is visible
                 return;
            }
            
            submitStatus.textContent = 'Submitting...';
            manualSubmitBtn.disabled = true; // Disable button during request
            manualSubmitBtn.textContent = 'Running...'; // Change button text

            try {
                const response = await fetch('/api/v1/local/submit', { 
                    method: 'POST',
                    headers: {
                         // Add headers if needed, e.g., CSRF if you implement that later
                         'Content-Type': 'application/json' 
                    },
                    // body: JSON.stringify({ }) // Add body if sending data
                 });
                
                const result = await response.json();
                
                // Display formatted result
                let output = `Status: ${response.status}\nSuccess: ${result.success}\n`;
                if (result.message) {
                    output += `Message: ${result.message}\n`;
                }
                if (result.error) {
                    output += `Error: ${result.error}\n`;
                }
                // Optionally include raw data for debugging
                // output += `\nRaw Response Data:\n${JSON.stringify(result.data, null, 2)}`;
                
                submitStatus.textContent = output;

                // Refresh config/status data after submit attempt to show updated timestamps etc.
                await initializeApp(); 

            } catch (error) {
                console.error('Error during manual submission:', error);
                submitStatus.textContent = `Error: Failed to trigger submission. Check console for details.\n${error}`;
                 // Optionally re-run initializeApp even on error? 
                 // await initializeApp(); 
            } finally {
                 manualSubmitBtn.disabled = false; // Re-enable button
                 manualSubmitBtn.textContent = 'Run Manual Submit'; // Restore button text
            }
        });
    }

    // Function to fetch config and update SPA
    async function fetchConfigAndUpdate() {
        try {
            const response = await fetch('/api/v1/local/config');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();

            if (result.success && result.data) {
                const config = result.data;
                // Update Account section
                document.getElementById('email').value = config.user.email || '';
                document.getElementById('token').value = config.user.token || '';
                document.getElementById('codes_suffix').value = config.user.codes_url_suffix || 'api/app/active/yrk/cs/2';
                document.getElementById('checkout_api_url_display').textContent = config.checkout_api_url || 'Not Set';
                updateFullUrlPreview(); // Update preview based on fetched data

                // Update Status display (ensure these elements exist in your HTML)
                const lastRefreshEl = document.getElementById('last-session-refresh'); 
                const lastAttemptEl = document.getElementById('last-code-attempt');
                const untriedCountEl = document.getElementById('untried-codes-count');
                const triedCountEl = document.getElementById('tried-codes-count'); // Make sure this element exists or add it

                if (lastRefreshEl) lastRefreshEl.textContent = config.state.last_session_refresh ? formatTimestamp(config.state.last_session_refresh) : 'Never';
                if (lastAttemptEl) lastAttemptEl.textContent = config.state.last_code_attempt ? formatTimestamp(config.state.last_code_attempt) : 'Never';
                if (untriedCountEl) untriedCountEl.textContent = config.state.available_untried_codes_count !== undefined ? config.state.available_untried_codes_count : 'N/A';
                if (triedCountEl) triedCountEl.textContent = config.state.tried_codes_count !== undefined ? config.state.tried_codes_count : 'N/A';

                // Update Logs section
                updateLogs(config.logs || []);

                // Check if user details are present and enable/disable navigation
                if (config.user.email && config.user.token && config.checkout_api_url) {
                    enableNavigation();
                } else {
                    disableNavigation(); // Implement or ensure disableNavigation exists
                }

                // Show saved message if applicable (using placeholder element)
                const urlParams = new URLSearchParams(window.location.search);
                const warningPlaceholder = document.getElementById('config-warning-placeholder');
                if (urlParams.get('saved') === 'true') {
                    displayMessage('Configuration saved successfully!', 'success', warningPlaceholder);
                     // Clean the URL
                    window.history.replaceState({}, document.title, window.location.pathname);
                } else if (urlParams.get('save_error') === 'true') {
                     displayMessage('Failed to save configuration. Check server logs.', 'error', warningPlaceholder);
                     // Clean the URL
                     window.history.replaceState({}, document.title, window.location.pathname);
                }

            } else {
                console.error('Failed to fetch or parse config:', result.message || 'Unknown error');
                displayMessage(`Error loading configuration: ${result.message || 'Unknown error'}`, 'error', document.getElementById('config-warning-placeholder'));
                disableNavigation(); 
            }
        } catch (error) {
            console.error('Error fetching config:', error);
            displayMessage(`Network or server error loading configuration: ${error.message}`, 'error', document.getElementById('config-warning-placeholder'));
            disableNavigation();
        }
    }

    // Function to update the logs section
    function updateLogs(logs) {
        const logsContent = document.getElementById('logs-content');
        if (!logsContent) {
            console.error('Logs content area not found');
            return;
        }

        logsContent.innerHTML = ''; // Clear existing logs

        if (!logs || logs.length === 0) {
            logsContent.innerHTML = '<p>No log entries found.</p>';
            return;
        }

        // Sort logs by timestamp descending (newest first)
        const sortedLogs = logs.sort((a, b) => {
            const dateA = new Date(a.timestamp);
            const dateB = new Date(b.timestamp);
            if (isNaN(dateA) && isNaN(dateB)) return 0;
            if (isNaN(dateA)) return 1; 
            if (isNaN(dateB)) return -1; 
            return dateB - dateA;
        });

        const table = document.createElement('table');
        table.className = 'logs-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Status</th>
                    <th>Message</th>
                </tr>
            </thead>
        `;
        const tbody = document.createElement('tbody');

        sortedLogs.forEach(log => {
            const row = tbody.insertRow();
            row.className = `log-status-${(log.status || 'info').toLowerCase()}`;

            const timeCell = row.insertCell();
            timeCell.textContent = formatTimestamp(log.timestamp);
            timeCell.style.whiteSpace = 'nowrap';

            const statusCell = row.insertCell();
            statusCell.textContent = log.status || 'info';
            statusCell.className = 'log-status-cell';

            const messageCell = row.insertCell();
            messageCell.textContent = log.message || ''; 
        });

        table.appendChild(tbody);
        logsContent.appendChild(table);
    }

    // Helper function to display messages (ensure this exists)
    function displayMessage(message, type = 'info', containerElement) {
        if (!containerElement) containerElement = document.getElementById('message-container'); // Default container
        if (!containerElement) return; // Exit if no container
        
        containerElement.textContent = message;
        containerElement.className = `message message-${type}`; // 'message-info', 'message-success', 'message-error'
        containerElement.style.display = 'block';

        // Optional: Auto-hide after a delay
        // setTimeout(() => { containerElement.style.display = 'none'; }, 5000);
    }

    // Add placeholder functions if they don't exist, or ensure they are implemented
    function enableNavigation() {
        console.log("Navigation enabled.");
        document.querySelectorAll('.sidebar nav a').forEach(link => link.classList.remove('disabled'));
    }

    function disableNavigation() {
        console.log("Navigation disabled.");
        document.querySelectorAll('.sidebar nav a:not([data-section="account"])') // Keep account link active
            .forEach(link => link.classList.add('disabled'));
    }

    function updateFullUrlPreview() {
        // Ensure this function properly updates the URL preview
        const base = document.getElementById('checkout_api_url_display').textContent || '';
        const suffix = document.getElementById('codes_suffix').value || '';
        const fullUrlEl = document.getElementById('full-codes-url');
        const previewLink = document.getElementById('preview-link');
        if (base && suffix && fullUrlEl && previewLink) {
            let fullUrl = base;
            if (base.endsWith('/') && suffix.startsWith('/')) {
                fullUrl += suffix.substring(1);
            } else if (!base.endsWith('/') && !suffix.startsWith('/')) {
                fullUrl += '/' + suffix;
            } else {
                fullUrl += suffix;
            }
            fullUrlEl.textContent = fullUrl;
            previewLink.href = fullUrl;
        } else if (fullUrlEl) {
            fullUrlEl.textContent = '';
            if (previewLink) previewLink.href = '#';
        }
    }
}); 