// api.js - Frontend API Integration Module
// Add this to your Word Heist frontend

class WordHeistAPI {
    constructor() {
        // Use environment variable or default to production URL
        this.baseURL = process.env.API_URL || 'https://your-backend-url.com/api';
        // For local development: 'http://localhost:5000/api'
        
        this.token = localStorage.getItem('wordheist_token');
        this.user = JSON.parse(localStorage.getItem('wordheist_user') || 'null');
    }

    // Helper method for API requests
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const config = {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            }
        };

        // Add auth token if available
        if (this.token) {
            config.headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'API request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Authentication methods
    async register(username, email, password) {
        const data = await this.request('/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });

        this.token = data.token;
        this.user = data.user;
        localStorage.setItem('wordheist_token', this.token);
        localStorage.setItem('wordheist_user', JSON.stringify(this.user));

        return data;
    }

    async login(email, password) {
        const data = await this.request('/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });

        this.token = data.token;
        this.user = data.user;
        localStorage.setItem('wordheist_token', this.token);
        localStorage.setItem('wordheist_user', JSON.stringify(this.user));

        return data;
    }

    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('wordheist_token');
        localStorage.removeItem('wordheist_user');
    }

    isAuthenticated() {
        return !!this.token;
    }

    // Game methods
    async getDailyPuzzle(date = null) {
        const params = date ? `?date=${date}` : '';
        return await this.request(`/daily-puzzle${params}`);
    }

    async validateWord(word, puzzleId) {
        return await this.request('/validate-word', {
            method: 'POST',
            body: JSON.stringify({ word, puzzle_id: puzzleId })
        });
    }

    async useHint(puzzleId) {
        return await this.request('/use-hint', {
            method: 'POST',
            body: JSON.stringify({ puzzle_id: puzzleId })
        });
    }

    async submitScore(puzzleId, score, timeTaken, wordsFound) {
        return await this.request('/submit-score', {
            method: 'POST',
            body: JSON.stringify({
                puzzle_id: puzzleId,
                score,
                time_taken: timeTaken,
                words_found: wordsFound
            })
        });
    }

    // Stats and leaderboard
    async getLeaderboard(period = 'daily', puzzleId = null) {
        const params = new URLSearchParams({ period });
        if (puzzleId) params.append('puzzle_id', puzzleId);
        
        return await this.request(`/leaderboard?${params}`);
    }

    async getUserStats() {
        return await this.request('/user-stats');
    }

    // Premium features
    async subscribe() {
        return await this.request('/subscribe', {
            method: 'POST'
        });
    }
}

// Initialize API instance
const api = new WordHeistAPI();

// ============= INTEGRATION WITH EXISTING GAME =============

// Updated game state with API integration
let enhancedGameState = {
    ...gameState,  // Keep existing game state
    puzzleId: null,
    isAuthenticated: false,
    dailyPuzzle: null
};

// Initialize game with API
async function initializeGame() {
    try {
        // Check if user is logged in
        enhancedGameState.isAuthenticated = api.isAuthenticated();
        
        // Get daily puzzle
        const puzzleData = await api.getDailyPuzzle();
        enhancedGameState.dailyPuzzle = puzzleData.puzzle;
        enhancedGameState.puzzleId = puzzleData.puzzle.id;
        
        // Update game with puzzle data
        enhancedGameState.letters = puzzleData.puzzle.letters;
        
        // If user has progress, restore it
        if (puzzleData.user_progress) {
            enhancedGameState.foundWords = puzzleData.user_progress.found_words;
            enhancedGameState.score = puzzleData.user_progress.current_score;
            enhancedGameState.hints = api.user ? 
                (api.user.premium ? 999 : api.user.hints_remaining) : 3;
        }
        
        // Update UI
        updateGameDisplay();
        
    } catch (error) {
        console.error('Failed to initialize game:', error);
        // Fall back to offline mode
        initGame();  // Use existing offline initialization
    }
}

// Enhanced word submission with API
async function submitWordWithAPI() {
    const word = enhancedGameState.currentWord.map(l => l.letter).join('');
    
    if (api.isAuthenticated() && enhancedGameState.puzzleId) {
        try {
            const result = await api.validateWord(word, enhancedGameState.puzzleId);
            
            if (result.valid && !result.duplicate) {
                enhancedGameState.foundWords = result.found_words;
                enhancedGameState.score = result.current_score;
                
                if (result.is_mystery) {
                    showMessage('Mystery Solved! +100 points!', 'success');
                    // Trigger win condition
                    if (result.completed) {
                        await handleGameComplete();
                    }
                } else {
                    showMessage(`+${result.points} points!`, 'success');
                }
                
                updateFoundWords();
                updateDisplay();
                clearWord();
            } else if (result.duplicate) {
                showMessage('Already found!', 'error');
            } else {
                showMessage('Not a valid word!', 'error');
            }
        } catch (error) {
            console.error('API validation failed:', error);
            // Fall back to offline validation
            submitWord();
        }
    } else {
        // Use offline validation
        submitWord();
    }
}

// Enhanced hint system with API
async function useHintWithAPI() {
    if (api.isAuthenticated() && enhancedGameState.puzzleId) {
        try {
            const result = await api.useHint(enhancedGameState.puzzleId);
            showMessage(`Try finding: ${result.hint}`, 'info');
            
            // Update remaining hints
            if (result.hints_remaining !== 'unlimited') {
                enhancedGameState.hints = result.hints_remaining;
                updateDisplay();
            }
        } catch (error) {
            console.error('Hint request failed:', error);
            showMessage(error.message, 'error');
        }
    } else {
        // Use offline hint system
        useHint();
    }
}

// Handle game completion
async function handleGameComplete() {
    const timeTaken = Math.floor((Date.now() - enhancedGameState.startTime) / 1000);
    
    try {
        await api.submitScore(
            enhancedGameState.puzzleId,
            enhancedGameState.score,
            timeTaken,
            enhancedGameState.foundWords
        );
        
        // Show completion message
        showCompletionModal();
        
        // Load leaderboard
        const leaderboard = await api.getLeaderboard('daily', enhancedGameState.puzzleId);
        showLeaderboard(leaderboard);
        
    } catch (error) {
        console.error('Failed to submit score:', error);
    }
}

// ============= UI COMPONENTS =============

// Login/Register Modal
function showAuthModal() {
    const modal = document.createElement('div');
    modal.className = 'auth-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <h2>Sign In to Save Progress</h2>
            <div class="auth-tabs">
                <button class="tab-btn active" onclick="showLoginForm()">Login</button>
                <button class="tab-btn" onclick="showRegisterForm()">Register</button>
            </div>
            <form id="authForm">
                <div id="loginFields">
                    <input type="email" id="email" placeholder="Email" required>
                    <input type="password" id="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </div>
            </form>
            <button class="close-btn" onclick="closeAuthModal()">×</button>
        </div>
    `;
    document.body.appendChild(modal);
}

// Leaderboard Display
function showLeaderboard(data) {
    const leaderboardEl = document.createElement('div');
    leaderboardEl.className = 'leaderboard-modal';
    leaderboardEl.innerHTML = `
        <div class="leaderboard-content">
            <h2>🏆 Daily Leaderboard</h2>
            <div class="leaderboard-list">
                ${data.leaderboard.map(entry => `
                    <div class="leaderboard-entry">
                        <span class="rank">#${entry.rank}</span>
                        <span class="username">${entry.username}</span>
                        <span class="score">${entry.score}</span>
                    </div>
                `).join('')}
            </div>
            <button onclick="closeLeaderboard()">Close</button>
        </div>
    `;
    document.body.appendChild(leaderboardEl);
}

// User Stats Display
async function showUserStats() {
    if (!api.isAuthenticated()) {
        showAuthModal();
        return;
    }
    
    try {
        const stats = await api.getUserStats();
        const statsEl = document.createElement('div');
        statsEl.className = 'stats-modal';
        statsEl.innerHTML = `
            <div class="stats-content">
                <h2>📊 Your Stats</h2>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-value">${stats.streak}</div>
                        <div class="stat-label">Day Streak</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.total_score}</div>
                        <div class="stat-label">Total Score</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.puzzles_solved}</div>
                        <div class="stat-label">Puzzles Solved</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.average_score}</div>
                        <div class="stat-label">Average Score</div>
                    </div>
                </div>
                ${!stats.premium ? `
                    <button class="premium-btn" onclick="showPremiumModal()">
                        ⭐ Upgrade to Premium
                    </button>
                ` : '<div class="premium-badge">⭐ Premium Member</div>'}
                <button onclick="closeStatsModal()">Close</button>
            </div>
        `;
        document.body.appendChild(statsEl);
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Export for use in HTML
window.WordHeistAPI = WordHeistAPI;
window.api = api;
window.initializeGame = initializeGame;
window.submitWordWithAPI = submitWordWithAPI;
window.useHintWithAPI = useHintWithAPI;
window.showUserStats = showUserStats;