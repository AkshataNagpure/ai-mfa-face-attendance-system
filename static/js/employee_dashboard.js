// Set Chart.js defaults for Dark Theme
if (window.Chart) {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
}

// ---------------- ATTENDANCE CHART ----------------
const attendanceCtx = document.getElementById('attendanceChart');
if (attendanceCtx && attendanceData) {
    const dates = Object.keys(attendanceData).sort();
    if (dates.length > 0) {
        const presentData = dates.map(date => attendanceData[date]?.present || 0);
        const absentData = dates.map(date => attendanceData[date]?.absent || 0);

        new Chart(attendanceCtx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Present',
                        data: presentData,
                        borderColor: '#50c878',
                        backgroundColor: 'rgba(80, 200, 120, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Absent',
                        data: absentData,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: { y: { beginAtZero: true } }
            }
        });
    }
}

// ---------------- EMOTION CHART ----------------
const emotionCtx = document.getElementById('emotionChart');
if (emotionCtx && emotionData) {
    const countsEntries = Object.entries(emotionData).filter(([, count]) => count > 0);
    if (countsEntries.length > 0) {
        const emotions = countsEntries.map(([emotion]) => emotion);
        const counts = countsEntries.map(([, count]) => count);

        // Dynamic color generator for any number of emotions
        const baseColors = [
            '#e74c3c', '#f39c12', '#3498db', '#50c878', 
            '#9b59b6', '#1abc9c', '#95a5a6', '#d35400',
            '#2ecc71', '#2980b9', '#8e44ad', '#16a085'
        ];
        const colors = emotions.map((_, i) => baseColors[i % baseColors.length]);

        new Chart(emotionCtx, {
            type: 'doughnut',
            data: {
                labels: emotions.map(e => e.charAt(0).toUpperCase() + e.slice(1)),
                datasets: [{
                    data: counts,
                    backgroundColor: colors
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }
}

// ---------------- AI CHAT ----------------
let welcomeMessageAdded = false;

function toggleTrackHub() {
    const chatWin = document.getElementById('trackhubWindow');
    const trigger = document.getElementById('trackhubTrigger');
    if (!chatWin) return;

    if (chatWin.style.display === 'flex') {
        chatWin.style.display = 'none';
        trigger.innerHTML = '💬';
    } else {
        chatWin.style.display = 'flex';
        trigger.innerHTML = '✕';
        
        // Auto-add welcome greeting if first time opening
        if (!welcomeMessageAdded) {
            addChatMessage("Hello! I'm TrackHub, your AI assistant. Ask me about your attendance status, emotion trends, or summaries!", 'assistant');
            welcomeMessageAdded = true;
        }
        
        // Auto-focus input
        const input = document.getElementById('chatInput');
        if (input) {
            setTimeout(() => input.focus(), 100);
        }
    }
}

function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    addChatMessage(message, 'user');
    input.value = '';

    fetch('/api/ai_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success && data.response) {
            const msg = data.response.replaceAll('**', '').replace(/\p{Emoji_Presentation}|\p{Extended_Pictographic}/gu, '').trim();
            addChatMessage(msg, 'assistant');
        } else {
            addChatMessage('Sorry, I encountered an error.', 'assistant');
        }
    })
    .catch(err => {
        console.error('AI Chat Error:', err);
        addChatMessage('Sorry, I encountered an error.', 'assistant');
    });
}

function addChatMessage(message, sender) {
    const messagesDiv = document.getElementById('chatMessages');
    if (!messagesDiv) return;
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    messageDiv.textContent = message;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ---------------- ENTER KEY SUPPORT ----------------
document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }
});

// ---------------- ATTENDANCE REPORT ----------------
function fetchAttendanceReport() {
    const selectedDate = document.getElementById('reportDateSelect').value;
    const resultArea = document.getElementById('attendanceReportResult');
    const emptyArea = document.getElementById('attendanceReportEmpty');
    
    if (!selectedDate) {
        resultArea.style.display = 'none';
        emptyArea.style.display = 'none';
        return;
    }
    
    fetch(`/api/get-attendance?date=${selectedDate}`)
        .then(response => response.json())
        .then(data => {
            if (!data.success || data.is_absent || data.is_holiday || data.is_not_registered) {
                resultArea.style.display = 'none';
                emptyArea.style.display = 'block';
                
                if (data.is_not_registered) {
                    emptyArea.innerHTML = `
                        <div style="font-size: 1.4rem; font-weight: bold; color: #94a3b8; margin-bottom: 5px;">👤 Status: Not Registered</div>
                        <div style="font-size: 1rem; color: #7f8c8d;">${data.message || 'You were not registered on this date.'}</div>
                    `;
                } else if (data.is_holiday) {
                    emptyArea.innerHTML = `
                        <div style="font-size: 1.4rem; font-weight: bold; color: #3498db; margin-bottom: 5px;">🌞 Status: Sunday Holiday</div>
                        <div style="font-size: 1rem; color: #7f8c8d;">${data.message || 'It\'s Sunday — a weekend holiday! No attendance recorded.'}</div>
                    `;
                } else {
                    emptyArea.innerHTML = `
                        <div style="font-size: 1.4rem; font-weight: bold; color: #e74c3c; margin-bottom: 5px;">🔴 Status: Absent</div>
                        <div style="font-size: 1rem; color: #7f8c8d;">No attendance recordings found for ${data.date || selectedDate}.</div>
                    `;
                }
                return;
            }
            
            // Populate fields
            document.getElementById('r_in').textContent = data.mark_in;
            document.getElementById('r_out').textContent = data.mark_out;
            document.getElementById('r_bout').textContent = data.break_out;
            document.getElementById('r_bin').textContent = data.break_in;
            
            document.getElementById('r_wh').textContent = data.metrics.working_time;
            document.getElementById('r_bd').textContent = data.metrics.break_duration;
            document.getElementById('r_ot').textContent = data.metrics.overtime;
            
            // Handle Badges
            const badgesDiv = document.getElementById('reportBadges');
            badgesDiv.innerHTML = '';
            
            if (data.flags.on_time) {
                badgesDiv.innerHTML += '<span style="background:#2ecc71; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">On Time</span>';
            }
            if (data.flags.late_entry) {
                badgesDiv.innerHTML += '<span style="background:#f39c12; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Late Entry</span>';
            }
            if (data.flags.early_exit) {
                badgesDiv.innerHTML += '<span style="background:#e74c3c; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Early Exit</span>';
            }
            if (data.flags.has_overtime) {
                badgesDiv.innerHTML += '<span style="background:#3498db; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Overtime</span>';
            }
            if (data.flags.incomplete_session) {
                badgesDiv.innerHTML += '<span style="background:#e74c3c; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Incomplete Session</span>';
            }
            if (data.flags.forgot_break_in) {
                badgesDiv.innerHTML += '<span style="background:#e67e22; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Forgot Break In</span>';
            }
            if (data.flags.short_break) {
                badgesDiv.innerHTML += '<span style="background:#f1c40f; color:black; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Short Break</span>';
            }
            if (data.flags.early_break) {
                badgesDiv.innerHTML += '<span style="background:#8e44ad; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Early Break</span>';
            }
            if (data.flags.late_break) {
                badgesDiv.innerHTML += '<span style="background:#2c3e50; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem;">Late Break</span>';
            }
            
            emptyArea.style.display = 'none';
            resultArea.style.display = 'block';
        })
        .catch(error => {
            console.error('Error fetching report:', error);
            resultArea.style.display = 'none';
            emptyArea.style.display = 'block';
            emptyArea.textContent = 'Error fetching data. Please try again later.';
        });
}

async function updateMonthlySummary() {
    const [month, year] = document.getElementById('summaryMonthSelect').value.split('-');
    const presentEl = document.getElementById('summaryPresent');
    const absentEl = document.getElementById('summaryAbsent');
    const totalEl = document.getElementById('summaryTotal');
    const fullDayEl = document.getElementById('summaryFullDay');
    const halfDayEl = document.getElementById('summaryHalfDay');
    const percentEl = document.getElementById('summaryPercentage');

    try {
        const response = await fetch(`/api/attendance/monthly-stats?month=${month}&year=${year}`);
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            presentEl.textContent = stats.present_count;
            absentEl.textContent = stats.absent_count;
            totalEl.textContent = stats.total_working_days;
            fullDayEl.textContent = stats.full_day;
            halfDayEl.textContent = stats.half_day;
            percentEl.textContent = `${stats.percentage}%`;
        }
    } catch (error) {
        console.error('Error updating monthly summary:', error);
    }
}

// Initialize monthly summary on load
document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const monthSelect = document.getElementById('summaryMonthSelect');
    if (monthSelect) {
        monthSelect.value = `${now.getMonth() + 1}-${now.getFullYear()}`;
        updateMonthlySummary();
    }
});
