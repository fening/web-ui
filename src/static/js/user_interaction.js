// User interaction handler
class UserInteractionHandler {
    constructor() {
        this.interactionModal = null;
        this.pendingInteractions = {};
        this.checkInterval = null;
        this.initialized = false;
    }

    init() {
        if (this.initialized) return;
        
        console.log("Initializing user interaction handler...");
        
        // Create modal element if it doesn't exist
        if (!document.getElementById('user-interaction-modal')) {
            this.createModalElement();
            console.log("Created modal element");
        }

        // Make sure Bootstrap is available
        if (typeof bootstrap === 'undefined') {
            console.error("Bootstrap is not loaded! Modal won't work.");
            // Try to load Bootstrap dynamically as a fallback
            this.loadBootstrap();
            return;
        }

        this.interactionModal = new bootstrap.Modal(document.getElementById('user-interaction-modal'));
        
        // Start checking for pending interactions
        this.checkInterval = setInterval(() => this.checkPendingInteractions(), 2000);
        this.initialized = true;
        
        console.log("User interaction handler initialized");
    }

    loadBootstrap() {
        // Try to load Bootstrap dynamically
        const cssLink = document.createElement('link');
        cssLink.rel = 'stylesheet';
        cssLink.href = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css';
        document.head.appendChild(cssLink);
        
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js';
        script.onload = () => {
            console.log("Bootstrap loaded dynamically");
            this.init();
        };
        document.head.appendChild(script);
    }

    createModalElement() {
        const modalHtml = `
            <div class="modal fade" id="user-interaction-modal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Agent needs your help</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p id="user-interaction-prompt"></p>
                            <p id="user-interaction-description" class="text-secondary"></p>
                            <div id="user-interaction-content">
                                <!-- Will be populated based on interaction type -->
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" id="cancel-interaction">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submit-interaction">Submit</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Add event listeners for keyboard shortcuts after modal is created
        document.getElementById('user-interaction-modal').addEventListener('keydown', (e) => {
            // Press Enter to submit
            if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey && !e.altKey) {
                const submitBtn = document.getElementById('submit-interaction');
                if (submitBtn && window.getComputedStyle(submitBtn).display !== 'none') {
                    submitBtn.click();
                }
            }
        });
    }

    async checkPendingInteractions() {
        try {
            console.log("Checking for pending interactions...");
            const response = await fetch('/api/interaction/pending');
            const data = await response.json();
            
            console.log("Pending interactions:", data);
            
            // Process any new interactions
            for (const [reqId, request] of Object.entries(data)) {
                if (!this.pendingInteractions[reqId]) {
                    console.log("New interaction request:", request);
                    this.pendingInteractions[reqId] = request;
                    this.showInteraction(request);
                    break; // Only show one at a time
                }
            }
        } catch (error) {
            console.error("Error checking for interactions:", error);
        }
    }

    showInteraction(request) {
        const promptEl = document.getElementById('user-interaction-prompt');
        const descEl = document.getElementById('user-interaction-description');
        const contentEl = document.getElementById('user-interaction-content');
        
        promptEl.textContent = request.prompt;
        descEl.textContent = request.description;
        
        // Clear previous content
        contentEl.innerHTML = '';
        
        // Create appropriate input based on interaction type
        switch (request.type) {
            case 'text_input':
                contentEl.innerHTML = `
                    <div class="mb-3">
                        <input type="text" class="form-control" id="interaction-input">
                    </div>
                `;
                break;
                
            case 'login':
                contentEl.innerHTML = `
                    <div class="alert alert-info">
                        <p>Please complete the login in the browser window.</p>
                        <p>Click "Done" when you've finished logging in.</p>
                    </div>
                `;
                // Change submit button text
                document.getElementById('submit-interaction').textContent = 'Done';
                break;
                
            case 'confirmation':
                contentEl.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="confirm-check">
                        <label class="form-check-label" for="confirm-check">
                            I confirm this action
                        </label>
                    </div>
                `;
                break;
                
            case 'selection':
                const options = request.options || [];
                const optionsHtml = options.map(option => 
                    `<div class="form-check">
                        <input class="form-check-input" type="radio" name="selection" value="${option}">
                        <label class="form-check-label">${option}</label>
                    </div>`
                ).join('');
                
                contentEl.innerHTML = `
                    <div class="mb-3">
                        ${optionsHtml}
                    </div>
                `;
                break;
                
            default:
                contentEl.innerHTML = `<p>Please provide the requested information.</p>`;
        }
        
        // Setup event listeners
        document.getElementById('submit-interaction').onclick = () => this.submitResponse(request);
        document.getElementById('cancel-interaction').onclick = () => this.cancelInteraction(request);
        
        // Show the modal
        this.interactionModal.show();
    }

    async submitResponse(request) {
        let response = null;
        
        switch (request.type) {
            case 'text_input':
                response = document.getElementById('interaction-input').value;
                break;
                
            case 'login':
                response = 'completed';
                break;
                
            case 'confirmation':
                response = document.getElementById('confirm-check').checked;
                break;
                
            case 'selection':
                const selected = document.querySelector('input[name="selection"]:checked');
                response = selected ? selected.value : null;
                break;
                
            default:
                response = 'acknowledged';
        }
        
        // Send response to backend
        try {
            const statusEl = document.getElementById('interaction-status');
            statusEl.textContent = 'Notifying agent of your action...';
            statusEl.className = 'alert alert-info mt-3';
            statusEl.style.display = 'block';

            await fetch('/api/interaction/response', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    request_id: request.request_id,
                    response: response,
                    cancelled: false
                })
            });

            // Remove from pending
            delete this.pendingInteractions[request.request_id];
            
            // Hide modal
            this.interactionModal.hide();

            // Show success message briefly
            statusEl.textContent = 'Agent notified! Continuing task...';
            statusEl.className = 'alert alert-success mt-3';

            // Wait a moment to show the success message
            await new Promise(resolve => setTimeout(resolve, 1500));
        } catch (error) {
            console.error("Error submitting response:", error);
            const statusEl = document.getElementById('interaction-status');
            statusEl.textContent = 'Error notifying agent: ' + error.message;
            statusEl.className = 'alert alert-danger mt-3';
        }
    }

    async cancelInteraction(request) {
        try {
            await fetch('/api/interaction/cancel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    request_id: request.request_id
                })
            });

            // Remove from pending
            delete this.pendingInteractions[request.request_id];
            
            // Hide modal
            this.interactionModal.hide();
        } catch (error) {
            console.error("Error cancelling interaction:", error);
        }
    }

    cleanup() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }
    }
}

const userInteractionHandler = new UserInteractionHandler();
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM loaded, initializing interaction handler");
    userInteractionHandler.init();
});

// Make sure initialization happens even if DOM is already loaded
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    console.log("DOM already loaded, initializing interaction handler immediately");
    setTimeout(() => {
        userInteractionHandler.init();
    }, 1000);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    userInteractionHandler.cleanup();
});
