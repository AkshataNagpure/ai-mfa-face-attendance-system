// Set Chart.js defaults for Dark Theme
if (window.Chart) {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
}

// ======================
// Statistics Chart
// ======================
const statsCtx = document.getElementById('statsChart');
if (statsCtx) {
    const totalEmployees = parseInt(statsCtx.dataset.totalEmployees || '0');
    const presentCount = parseInt(statsCtx.dataset.presentCount || '0');
    const absentCount = parseInt(statsCtx.dataset.absentCount || '0');

    new Chart(statsCtx, {
        type: 'doughnut',
        data: {
            labels: ['Present', 'Absent'],
            datasets: [{
                data: [presentCount, absentCount],
                backgroundColor: ['#50c878', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                }
            }
        }
    });
}

// ======================
// Emotion Trends Chart
// ======================
let emotionTrendsData = null;
const emotionTrendsDataElement = document.getElementById('emotionTrendsData');
if (emotionTrendsDataElement) {
    try {
        emotionTrendsData = JSON.parse(emotionTrendsDataElement.textContent);
    } catch (error) {
        console.error('Failed to parse emotion trends data:', error);
    }
}

const emotionTrendCtx = document.getElementById('emotionTrendChart');
const EXCLUDED_EMOTIONS = new Set(['not recorded', 'none', 'null', 'n/a', 'unknown']);
if (emotionTrendCtx && emotionTrendsData && emotionTrendsData.overall_emotions) {
    const countsEntries = Object.entries(emotionTrendsData.overall_emotions)
        .filter(([emotion, count]) => count > 0 && !EXCLUDED_EMOTIONS.has(emotion.toLowerCase().trim()));

    if (countsEntries.length > 0) {
        const emotions = countsEntries.map(([emotion]) => emotion);
        const counts = countsEntries.map(([, count]) => count);

        new Chart(emotionTrendCtx, {
            type: 'doughnut',
            data: {
                labels: emotions.map(e => e.charAt(0).toUpperCase() + e.slice(1)),
                datasets: [{
                    label: 'Emotion Frequency',
                    data: counts,
                    backgroundColor: ['#e74c3c', '#f39c12', '#3498db', '#50c878', '#9b59b6', '#1abc9c', '#95a5a6']
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

// ======================
// Face Image Modal
// ======================
function addFaceImages(userId) {
    document.getElementById('userIdInput').value = userId;
    document.getElementById('faceImagesModal').style.display = 'block';
}

function closeFaceImagesModal() {
    document.getElementById('faceImagesModal').style.display = 'none';
    document.getElementById('faceImagesForm').reset();
    document.getElementById('faceImagesResult').innerHTML = '';
}

// ======================
// Delete Employee
// ======================
function confirmDeleteEmployee(userId, name) {
    if (confirm(`Are you sure you want to delete ${name}? This will remove their face data, attendance, and notifications.`)) {
        deleteEmployee(userId);
    }
}

async function deleteEmployee(userId) {
    try {
        const response = await fetch(`/api/employees/${userId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.message || 'Failed to delete employee.');
        }
    } catch (error) {
        console.error('Error deleting employee:', error);
        alert('Error occurred while deleting employee.');
    }
}

// ======================
//  AI Chat Assistant
// ======================
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
        trigger.innerHTML = '❌';

        // Auto-add welcome greeting if first time opening
        if (!welcomeMessageAdded) {
            addChatMessage("Hello! I'm TrackHub, your AI assistant. Ask me about daily attendance lists, totals, or employee records!", 'assistant');
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
            const raw = data.success ? data.response : 'Error occurred.';
            const msg = raw.replaceAll('**', '').replace(/\p{Emoji_Presentation}|\p{Extended_Pictographic}/gu, '').trim();
            addChatMessage(msg, 'assistant');
        })
        .catch(err => {
            console.error(err);
            addChatMessage('Error occurred.', 'assistant');
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

// ======================
//  Event Listeners
// ======================
document.addEventListener('DOMContentLoaded', function () {
    // Enter key for chat
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }

    // Delete button in modal
    const deleteBtn = document.getElementById('deleteEmployeeBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', () => {
            if (currentDetailUserId) {
                const name = document.getElementById('detailName').textContent;
                confirmDeleteEmployee(currentDetailUserId, name);
            }
        });
    }

    // Real-time mobile number validation on Edit Profile
    const editMobileEl = document.getElementById('editMobile');
    const editMobileMsgEl = document.getElementById('editMobileMessage');
    if (editMobileEl && editMobileMsgEl) {
        editMobileEl.addEventListener('input', () => {
            const val = editMobileEl.value.trim();
            if (!val) {
                editMobileMsgEl.style.display = 'none';
                return;
            }
            if (val.length !== 10 || !/^\d{10}$/.test(val)) {
                editMobileMsgEl.style.display = 'block';
                editMobileMsgEl.style.color = '#ff7979';
                editMobileMsgEl.textContent = 'plz enter valid number (must be exactly 10 digits)';
            } else {
                editMobileMsgEl.style.display = 'block';
                editMobileMsgEl.style.color = '#50c878';
                editMobileMsgEl.textContent = 'Valid mobile number.';
            }
        });
    }
});

// ======================
//  Employee Details Logic
// ======================
let attendanceChartInstance = null;
let emotionChartInstance = null;
let currentDetailUserId = null;

async function viewEmployeeDetails(userId) {
    currentDetailUserId = userId;
    const modal = document.getElementById('employeeDetailsModal');
    modal.style.display = 'block';

    // Show loading state
    document.getElementById('detailName').textContent = 'Loading...';

    try {
        const response = await fetch(`/api/admin/employee_details/${userId}`);
        const data = await response.json();

        if (!data.success) {
            alert(data.message || 'Failed to fetch details');
            closeEmployeeDetailsModal();
            return;
        }

        const profile = data.profile;
        const stats = data.stats;
        const emotionTrend = data.emotion_trend;

        // Populate Profile Info
        document.getElementById('detailName').textContent = profile.name;
        document.getElementById('detailDept').textContent = profile.department;

        document.getElementById('detailFullName').textContent = profile.name;
        document.getElementById('detailUsername').textContent = profile.username;
        document.getElementById('detailEmail').textContent = profile.email;
        document.getElementById('detailMobile').textContent = profile.mobile;
        document.getElementById('detailDeptText').textContent = profile.department;

        // Populate Edit Form Fields
        document.getElementById('editName').value = profile.name;
        document.getElementById('editUsername').value = profile.username;
        document.getElementById('editEmail').value = profile.email;
        document.getElementById('editMobile').value = profile.mobile === 'N/A' ? '' : profile.mobile;
        document.getElementById('editDept').value = profile.department;
        document.getElementById('editPhoto').value = ''; // Reset file input

        // Ensure View Mode is active initially
        toggleEditProfile(false);

        // Avatar
        const avatarDiv = document.getElementById('detailAvatar');
        if (profile.image_url) {
            avatarDiv.innerHTML = `<img src="${profile.image_url}" alt="${profile.name}">`;
        } else {
            avatarDiv.innerHTML = `<div class="avatar-placeholder" style="width:100%; height:100%; border-radius:0;">${profile.name[0]}</div>`;
        }

        // Stats
        document.getElementById('detailPresent').textContent = stats.present;
        document.getElementById('detailAbsent').textContent = stats.absent;
        document.getElementById('detailTotal').textContent = stats.total;
        document.getElementById('detailFullDay').textContent = stats.full_day;
        document.getElementById('detailHalfDay').textContent = stats.half_day;

        // Charts
        renderDetailAttendanceChart(stats);
        renderDetailEmotionChart(emotionTrend);


        // Email Logs
        const emailDiv = document.getElementById('detailEmailLogs');
        if (data.email_logs && data.email_logs.length > 0) {
            emailDiv.innerHTML = data.email_logs.map(l => `
                <div class="mini-item">
                    <strong>${l.subject}</strong>
                    <div class="mini-item-meta">${l.sent_at} - Status: ${l.status}</div>
                </div>
            `).join('');
        } else {
            emailDiv.innerHTML = '<p class="text-muted">No email logs</p>';
        }

        // Reset and hide the detailed report section for the new employee
        document.getElementById('detailReportDateSelect').value = '';
        document.getElementById('detailAttendanceReportResult').style.display = 'none';
        document.getElementById('detailAttendanceReportEmpty').style.display = 'none';

        // Initialize monthly summary to current month
        const now = new Date();
        document.getElementById('summaryMonthSelect').value = `${now.getMonth() + 1}-${now.getFullYear()}`;
        updateMonthlySummary();

    } catch (error) {
        console.error('Error fetching employee details:', error);
        alert('An error occurred while fetching details.');
        closeEmployeeDetailsModal();
    }
}

function closeEmployeeDetailsModal() {
    document.getElementById('employeeDetailsModal').style.display = 'none';
    if (attendanceChartInstance) attendanceChartInstance.destroy();
    if (emotionChartInstance) emotionChartInstance.destroy();
    currentDetailUserId = null;
}

// ======================
//  Edit Employee Profile Info
// ======================
function toggleEditProfile(show) {
    const viewMode = document.getElementById('profileViewMode');
    const editForm = document.getElementById('profileEditForm');
    const editBtn = document.getElementById('editProfileBtn');

    if (!viewMode || !editForm || !editBtn) return;

    if (show) {
        viewMode.style.display = 'none';
        editForm.style.display = 'block';
        editBtn.style.display = 'none';
    } else {
        viewMode.style.display = 'block';
        editForm.style.display = 'none';
        editBtn.style.display = 'block';
        const editMobileMsgEl = document.getElementById('editMobileMessage');
        if (editMobileMsgEl) {
            editMobileMsgEl.style.display = 'none';
        }
    }
}

async function saveProfileEdits(event) {
    event.preventDefault();
    if (!currentDetailUserId) return;

    const mobileInput = document.getElementById('editMobile');
    if (mobileInput) {
        const mobileValue = mobileInput.value.trim();
        if (mobileValue !== "") {
            if (mobileValue.length !== 10 || !/^\d{10}$/.test(mobileValue)) {
                alert("plz enter valid number (must be exactly 10 digits)");
                mobileInput.focus();
                return;
            }
        }
    }

    const form = document.getElementById('profileEditForm');
    const formData = new FormData(form);

    try {
        const response = await fetch(`/api/admin/update_employee/${currentDetailUserId}`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            alert(data.message || 'Profile updated successfully!');
            window.location.reload();
        } else {
            alert(data.message || 'Failed to update profile.');
        }
    } catch (error) {
        console.error('Error saving profile edits:', error);
        alert('An error occurred while saving profile edits.');
    }
}

function renderDetailAttendanceChart(stats) {
    const ctx = document.getElementById('detailAttendanceChart').getContext('2d');
    if (attendanceChartInstance) attendanceChartInstance.destroy();

    attendanceChartInstance = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Present', 'Absent'],
            datasets: [{
                data: [stats.present, stats.absent],
                backgroundColor: ['#2ecc71', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

function renderDetailEmotionChart(emotionCounts) {
    const canvas = document.getElementById('detailEmotionChart');
    const ctx = canvas.getContext('2d');
    if (emotionChartInstance) emotionChartInstance.destroy();

    const EXCLUDED_EMOTIONS_DETAIL = new Set(['not recorded', 'none', 'null', 'n/a', 'unknown']);
    const countsEntries = Object.entries(emotionCounts)
        .filter(([emotion, count]) => count > 0 && !EXCLUDED_EMOTIONS_DETAIL.has(emotion.toLowerCase().trim()));

    if (countsEntries.length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = "14px 'Segoe UI'";
        ctx.fillStyle = "#666";
        ctx.textAlign = "center";
        ctx.fillText("No emotion data available", canvas.width / 2, canvas.height / 2);
        return;
    }

    const labels = countsEntries.map(([emotion]) => emotion);
    const counts = countsEntries.map(([, count]) => count);

    emotionChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
            datasets: [{
                label: 'Frequency',
                data: counts,
                backgroundColor: ['#e74c3c', '#f39c12', '#3498db', '#50c878', '#9b59b6', '#1abc9c', '#95a5a6']
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

async function updateMonthlySummary() {
    if (!currentDetailUserId) return;

    const [month, year] = document.getElementById('summaryMonthSelect').value.split('-');
    const presentEl = document.getElementById('detailPresent');
    const absentEl = document.getElementById('detailAbsent');
    const totalEl = document.getElementById('detailTotal');
    const fullDayEl = document.getElementById('detailFullDay');
    const halfDayEl = document.getElementById('detailHalfDay');
    const shortDayEl = document.getElementById('detailShortDay');
    const percentEl = document.getElementById('detailPercentage');
    const workingHoursEl = document.getElementById('detailWorkingHours');
    const overtimeHoursEl = document.getElementById('detailOvertimeHours');

    try {
        const response = await fetch(`/api/attendance/monthly-stats?employee_id=${currentDetailUserId}&month=${month}&year=${year}`);
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            presentEl.textContent = stats.present_count;
            absentEl.textContent = stats.absent_count;
            totalEl.textContent = stats.total_working_days;
            fullDayEl.textContent = stats.full_day;
            halfDayEl.textContent = stats.half_day;
            if (shortDayEl) shortDayEl.textContent = stats.short_day;
            percentEl.textContent = `${stats.percentage}%`;

            if (workingHoursEl) workingHoursEl.textContent = stats.working_time;
            if (overtimeHoursEl) overtimeHoursEl.textContent = stats.overtime;

            // Update the chart if it exists
            renderDetailAttendanceChart({
                present: stats.present_count,
                absent: stats.absent_count
            });
        }
    } catch (error) {
        console.error('Error updating monthly summary:', error);
    }
}

// ======================
//  Modal Close Handler
// ======================
window.onclick = function (e) {
    const faceModal = document.getElementById('faceImagesModal');
    const detailModal = document.getElementById('employeeDetailsModal');
    if (e.target === faceModal) {
        closeFaceImagesModal();
    }
    if (e.target === detailModal) {
        closeEmployeeDetailsModal();
    }
};

// ======================
//  Attendance Report Fetch
// ======================
// ======================
//  Attendance Report Fetch (Fixed)
// ======================
async function fetchAttendanceReport() {
    const dateInput = document.getElementById('reportDate');
    const reportSection = document.getElementById('attendanceReportSection');

    if (!dateInput || !reportSection) {
        console.error("Attendance report elements not found.");
        return;
    }

    const dateVal = dateInput.value;
    if (!dateVal) {
        reportSection.innerHTML = `<p class="text-danger">Please select a date.</p>`;
        return;
    }

    reportSection.innerHTML = `<p>Loading attendance data...</p>`;

    try {
        const res = await fetch(`/api/admin/attendance_report?date=${encodeURIComponent(dateVal)}`);
        const data = await res.json();

        if (!data.success) {
            reportSection.innerHTML = `<p class="text-danger">${data.message || "Error fetching report."}</p>`;
            return;
        }

        //  handle future and weekend cases
        if (data.special) {
            let alertClass = "alert-info";
            if (data.type === "holiday") alertClass = "alert-warning";
            if (data.type === "future") alertClass = "alert-secondary";

            reportSection.innerHTML = `
                <div class="alert ${alertClass}" role="alert">
                    ${data.message}
                </div>
            `;
            return;
        }

        //  Normal attendance data
        const report = data.report || { present: [], absent: [] };
        const present = report.present || [];
        const absent = report.absent || [];

        let html = `
            <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                <h4 class="mt-3"> Present Employees (${present.length})</h4>
                <table class="table table-striped table-bordered align-middle">
                    <thead><tr><th>Name</th><th>Department</th><th>Mark-In</th><th>Mark-Out</th></tr></thead>
                    <tbody>
                        ${present.map(p => `
                            <tr>
                                <td>${p.name}</td>
                                <td>${p.department}</td>
                                <td>${p.mark_in || '-'}</td>
                                <td>${p.mark_out || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>

                <h4 class="mt-4"> Absent Employees (${absent.length})</h4>
                <table class="table table-striped table-bordered align-middle">
                    <thead><tr><th>Name</th><th>Department</th></tr></thead>
                    <tbody>
                        ${absent.map(a => `
                            <tr>
                                <td>${a.name}</td>
                                <td>${a.department}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        reportSection.innerHTML = html;
    } catch (err) {
        console.error('Error:', err);
        reportSection.innerHTML = `<p class="text-danger">Server error while fetching attendance.</p>`;
    }
}

// ======================
//  Detailed Employee Attendance Report (Modal)
// ======================
async function fetchEmployeeDetailedReport() {
    const selectedDate = document.getElementById('detailReportDateSelect').value;
    const resultArea = document.getElementById('detailAttendanceReportResult');
    const emptyArea = document.getElementById('detailAttendanceReportEmpty');

    if (!selectedDate || !currentDetailUserId) {
        resultArea.style.display = 'none';
        emptyArea.style.display = 'none';
        return;
    }

    try {
        const response = await fetch(`/api/get-attendance?employee_id=${currentDetailUserId}&date=${selectedDate}`);
        const data = await response.json();

        if (!data.success || data.is_absent || data.is_holiday || data.is_not_registered) {
            resultArea.style.display = 'none';
            emptyArea.style.display = 'block';

            if (data.is_not_registered) {
                emptyArea.innerHTML = `
                    <div style="font-size: 1.4rem; font-weight: bold; color: #94a3b8; margin-bottom: 5px;"> Status: Not Registered</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">${data.message || 'Employee was not registered on this date.'}</div>
                `;
            } else if (data.is_holiday) {
                emptyArea.innerHTML = `
                    <div style="font-size: 1.4rem; font-weight: bold; color: #3498db; margin-bottom: 5px;"> Status: Sunday Holiday</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">${data.message || 'It\'s Sunday — a weekend holiday! No attendance recorded.'}</div>
                `;
            } else {
                emptyArea.innerHTML = `
                    <div style="font-size: 1.4rem; font-weight: bold; color: #e74c3c; margin-bottom: 5px;"> Status: Absent</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">No attendance recordings found for ${data.date || selectedDate}.</div>
                `;
            }
            return;
        }

        // Populate fields
        document.getElementById('dr_in').textContent = data.mark_in;
        document.getElementById('dr_out').textContent = data.mark_out;
        document.getElementById('dr_bout').textContent = data.break_out;
        document.getElementById('dr_bin').textContent = data.break_in;

        document.getElementById('dr_wh').textContent = data.metrics.working_time;
        document.getElementById('dr_bd').textContent = data.metrics.break_duration;
        document.getElementById('dr_ot').textContent = data.metrics.overtime;

        // Handle Badges
        const badgesDiv = document.getElementById('detailReportBadges');
        badgesDiv.innerHTML = '';

        // --- Mark In Badges ---
        if (data.flags.early_entry) {
            badgesDiv.innerHTML += '<span style="background:#3498db; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Early Entry</span>';
        } else if (data.flags.on_time_entry) {
            badgesDiv.innerHTML += '<span style="background:#2ecc71; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> On Time Entry</span>';
        } else if (data.flags.late_entry) {
            badgesDiv.innerHTML += '<span style="background:#e67e22; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Late Entry</span>';
        }

        // --- Break Out Badges ---
        if (data.flags.early_break) {
            badgesDiv.innerHTML += '<span style="background:#9b59b6; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Early Break</span>';
        } else if (data.flags.on_time_break) {
            badgesDiv.innerHTML += '<span style="background:#27ae60; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> On Time Break</span>';
        } else if (data.flags.late_break) {
            badgesDiv.innerHTML += '<span style="background:#2c3e50; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Late Break</span>';
        }

        // --- Break In Badges ---
        if (data.flags.long_break) {
            badgesDiv.innerHTML += '<span style="background:#e74c3c; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Long Break</span>';
        } else if (data.flags.early_break_return) {
            badgesDiv.innerHTML += '<span style="background:#1abc9c; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Early Break Return</span>';
        } else if (data.flags.on_time_break_return) {
            badgesDiv.innerHTML += '<span style="background:#27ae60; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> On Time Break Return</span>';
        } else if (data.flags.late_break_return) {
            badgesDiv.innerHTML += '<span style="background:#e67e22; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Late Break Return</span>';
        }

        // --- Mark Out Badges ---
        if (data.flags.early_exit) {
            badgesDiv.innerHTML += '<span style="background:#e74c3c; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Early Departure</span>';
        } else if (data.flags.on_time_exit) {
            badgesDiv.innerHTML += '<span style="background:#2ecc71; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> On Time Departure</span>';
        } else if (data.flags.late_exit) {
            badgesDiv.innerHTML += '<span style="background:#8e44ad; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Late Departure</span>';
        }

        // --- Other Badges (kept as-is) ---
        if (data.flags.has_overtime) {
            badgesDiv.innerHTML += '<span style="background:#3498db; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Overtime</span>';
        }
        if (data.flags.incomplete_session) {
            badgesDiv.innerHTML += '<span style="background:#e74c3c; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Incomplete Session</span>';
        }
        if (data.flags.forgot_break_in) {
            badgesDiv.innerHTML += '<span style="background:#e67e22; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Forgot Break In</span>';
        }
        if (data.flags.short_break) {
            badgesDiv.innerHTML += '<span style="background:#f1c40f; color:black; padding:4px 8px; border-radius:12px; font-size:0.8rem; margin-right:5px;"> Short Break</span>';
        }
        if (data.flags.admin_approval) {
            badgesDiv.innerHTML += '<span onclick="toggleAdminApprovalSection()" style="background:#e67e22; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; cursor:pointer; font-weight:bold; margin-right:5px;">Pending Admin Approval </span>';
        }
        if (data.flags.admin_approved) {
            badgesDiv.innerHTML += '<span style="background:#2ecc71; color:white; padding:4px 8px; border-radius:12px; font-size:0.8rem; font-weight:bold; margin-right:5px;">Admin Approved </span>';
        }

        // --- Day Type Badge ---
        if (data.flags.day_type) {
            let dtBg = '#16a085';
            if (data.flags.day_type === 'Full Day') dtBg = '#27ae60';
            else if (data.flags.day_type === 'Half Day') dtBg = '#e67e22';
            else if (data.flags.day_type === 'Short Day') dtBg = '#c0392b';
            badgesDiv.innerHTML += `<span style="background:${dtBg}; color:white; padding:4px 12px; border-radius:12px; font-size:0.82rem; font-weight:700; margin-right:5px; border: 2px solid rgba(255,255,255,0.3);">${data.flags.day_type}</span>`;
        }

        // Hide approval section by default
        const approvalSection = document.getElementById('adminApprovalSection');
        if (approvalSection) {
            approvalSection.style.display = 'none';
            const confirmCheck = document.getElementById('confirmApprovalCheck');
            if (confirmCheck) {
                confirmCheck.checked = false;
                confirmCheck.onchange = function() {
                    const enabled = this.checked;
                    ['btnApproveFull', 'btnApproveHalf', 'btnMarkAbsent'].forEach(id => {
                        const btn = document.getElementById(id);
                        if (btn) {
                            btn.disabled = !enabled;
                            btn.style.cursor = enabled ? 'pointer' : 'not-allowed';
                            btn.style.opacity = enabled ? '1' : '0.6';
                        }
                    });
                };
            }
            // Reset all buttons to disabled initially
            ['btnApproveFull', 'btnApproveHalf', 'btnMarkAbsent'].forEach(id => {
                const btn = document.getElementById(id);
                if (btn) {
                    btn.disabled = true;
                    btn.style.cursor = 'not-allowed';
                    btn.style.opacity = '0.6';
                }
            });
        }

        emptyArea.style.display = 'none';
        resultArea.style.display = 'block';
    } catch (error) {
        console.error('Error fetching detailed report:', error);
        resultArea.style.display = 'none';
        emptyArea.style.display = 'block';
        emptyArea.textContent = 'Error fetching data. Please try again later.';
    }
}


// ======================
//  Predictive Attendance Table
// ======================
async function fetchPredictiveAttendance() {
    const section = document.getElementById('predictiveAttendanceSection');
    if (!section) return;

    try {
        const res = await fetch('/api/admin/predictive_attendance');
        const data = await res.json();

        if (!data.success) {
            section.innerHTML = `<p class="text-danger">Failed to load predictive attendance.</p>`;
            return;
        }

        const predictions = data.predictions || [];
        if (predictions.length === 0) {
            section.innerHTML = `<p>No predictive data available.</p>`;
            return;
        }

        section.innerHTML = `
            <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                <h4 class="mt-3"> Predictive Attendance</h4>
                <table class="table table-bordered table-striped align-middle">
                    <thead><tr><th>Name</th><th>Department</th><th>Predicted Attendance</th><th>Confidence</th></tr></thead>
                    <tbody>
                        ${predictions.map(p => `
                            <tr>
                                <td>${p.name}</td>
                                <td>${p.department}</td>
                                <td>${p.predicted_status}</td>
                                <td>${p.confidence ? p.confidence.toFixed(2) + '%' : '-'}</td>
                            </tr>`).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        console.error('Error fetching predictive attendance:', err);
        section.innerHTML = `<p class="text-danger">Server error while fetching predictive attendance.</p>`;
    }
}

// ======================
//  Admin Approval Handlers
// ======================
function toggleAdminApprovalSection() {
    const section = document.getElementById('adminApprovalSection');
    if (section) {
        if (section.style.display === 'none') {
            section.style.display = 'block';
            section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            section.style.display = 'none';
        }
    }
}
window.toggleAdminApprovalSection = toggleAdminApprovalSection;

async function submitAdminDecision(decision) {
    const selectedDate = document.getElementById('detailReportDateSelect').value;
    if (!currentDetailUserId || !selectedDate) {
        alert('Please select a date first.');
        return;
    }
    const confirmCheck = document.getElementById('confirmApprovalCheck');
    if (!confirmCheck || !confirmCheck.checked) {
        alert('Please check the confirmation box first.');
        return;
    }

    if (!confirm(`Are you sure you want to approve this record as a ${decision.replace('_', ' ')}?`)) {
        return;
    }

    try {
        const response = await fetch('/api/admin/approve_attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                employee_id: currentDetailUserId,
                date: selectedDate,
                decision: decision
            })
        });
        const result = await response.json();
        if (result.success) {
            alert(result.message);
            // Hide approval section
            const section = document.getElementById('adminApprovalSection');
            if (section) section.style.display = 'none';
            // Re-fetch detailed report
            await fetchEmployeeDetailedReport();
            // Re-fetch monthly stats
            await updateMonthlySummary();
        } else {
            alert('Error: ' + result.message);
        }
    } catch (err) {
        console.error('Error submitting approval:', err);
        alert('An error occurred. Please try again.');
    }
}
window.submitAdminDecision = submitAdminDecision;
