document.addEventListener('DOMContentLoaded', () => {
    const totalUsersElem = document.getElementById('total-users');
    const followedCountElem = document.getElementById('followed-count');
    const unfollowedCountElem = document.getElementById('unfollowed-count');
    const disqualifiedCountElem = document.getElementById('disqualified-count');
    const logListElem = document.getElementById('log-list');

    async function fetchData() {
        try {
            const response = await fetch('/api/data');
            const data = await response.json();

            if (response.ok) {
                totalUsersElem.textContent = data.total_users;
                followedCountElem.textContent = data.followed_count;
                unfollowedCountElem.textContent = data.unfollowed_count;
                disqualifiedCountElem.textContent = data.disqualified_count;

                logListElem.innerHTML = ''; // Clear previous logs
                data.recent_logs.forEach(log => {
                    const listItem = document.createElement('li');
                    listItem.className = log.level; // Add level as class for styling
                    listItem.innerHTML = `
                        <span class="timestamp">${new Date(log.timestamp).toLocaleTimeString()}</span>
                        <span class="level ${log.level}">${log.level}</span>
                        ${log.message}
                    `;
                    logListElem.appendChild(listItem);
                });
            } else {
                console.error('API Error:', data.error);
                // Display error on dashboard
                totalUsersElem.textContent = 'Error';
                followedCountElem.textContent = 'Error';
                unfollowedCountElem.textContent = 'Error';
                disqualifiedCountElem.textContent = 'Error';
                logListElem.innerHTML = `<li class="ERROR">Failed to load data: ${data.error}</li>`;
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            // Display error on dashboard
            totalUsersElem.textContent = 'Error';
            followedCountElem.textContent = 'Error';
            unfollowedCountElem.textContent = 'Error';
            disqualifiedCountElem.textContent = 'Error';
            logListElem.innerHTML = `<li class="ERROR">Network error: ${error.message}</li>`;
        }
    }

    // Fetch data immediately and then every 5 seconds
    fetchData();
    setInterval(fetchData, 5000); // Refresh every 5 seconds
});
