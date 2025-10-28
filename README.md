# Project Reach 
[![Reach Bot Controller](https://github.com/felicityblueish/reach/actions/workflows/bot_controller.yml/badge.svg)](https://github.com/felicityblueish/reach/actions/workflows/bot_controller.yml)

> *"This project was inspired by the challenges of building products only to see them fail to reach their potential due to marketing hurdles and competition. My goal was to create a tool that is less about marketing and more about product delivery—connecting with users who have a genuine, immediate need. This is vital for respecting the GitHub ecosystem long-term. If you use or fork this project, please do so responsibly."*

---

A configurable GitHub bot designed to strategically connect with users by identifying those who have just started projects that your product can help with. The bot is built to be reliable, stateful, and respectful of GitHub's rate limits.

## Features

- **Precision User Targeting**: Uses a focused search query to find users who have recently created repositories with specific keywords (e.g., "portfolio"), have a low follower count, and are active within a recent timeframe.
- **Event-Driven Discovery**: In addition to searching for new repositories, the bot also monitors public GitHub events to find users who have recently starred or forked relevant projects.
- **Stealthy & Rate-Limit Aware**: Operates with randomized delays between actions and intelligently respects GitHub API rate limits to ensure account safety and long-term sustainability.
- **Stateful & Smart**: Uses an SQLite database to remember which users have been processed, followed, or disqualified, preventing duplicate actions.
- **Fully Automated**: Runs on a schedule using GitHub Actions. Set it up once, and it will run automatically.
- **Highly Configurable**: Easily change all operational parameters, delays, and targeting criteria by editing simple YAML configuration files.
- **Monitoring Dashboard**: Includes a local web dashboard to monitor the bot's activity and view its current settings in real-time.

## Technology Stack

- **Language:** Python 3.12+
- **GitHub API Wrapper:** httpx (for asynchronous requests)
- **Database:** SQLite with SQLAlchemy
- **Configuration:** PyYAML
- **Scheduling:** GitHub Actions
- **Dashboard:** Flask

## Getting Started: Deployment Guide

Follow these steps to get your bot running.

### 1. Create a GitHub Personal Access Token (PAT)

The bot needs a PAT to authenticate with the GitHub API.

1.  Go to your GitHub account's **Settings** > **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
2.  Click **"Generate new token"** and select **"Generate new token (classic)"**.
3.  Give the token a descriptive name (e.g., `REACH_BOT_TOKEN`).
4.  Set the **Expiration** to "No expiration".
5.  Under **Scopes**, check the main **`user`** scope. This will automatically select `read:user` and `user:follow`.
6.  Click **"Generate token"** and copy the token immediately. You will not see it again.

### 2. Add the Token to Repository Secrets

1.  In your GitHub repository for this project, go to `Settings` > `Secrets and variables` > `Actions`.
2.  Click **`New repository secret`**.
3.  Set the **Name** to exactly `REACH_BOT_TOKEN`.
4.  Paste your copied token into the **Secret** field.
5.  Click **`Add secret`**.

### 3. Run the Bot

The bot is now ready to be activated. It is scheduled to run automatically, but you can trigger the first run manually.

1.  Go to the **`Actions`** tab of your repository.
2.  Click on the **"Reach Bot Controller"** workflow in the left sidebar.
3.  Click the **`Run workflow`** dropdown on the right, and then click the green **`Run workflow`** button.

After this, the bot will run on its schedule. You can monitor its progress in the Actions tab.

## Configuration

You can customize the bot's behavior by editing the files in the `config/` directory.

-   **`config/settings.yml`**: Control the bot's operational parameters. Adjust the min/max delays between actions, the number of users to process per run, and the rate limit safety buffer.
-   **`config/criteria.yml`**: Define your target audience and disqualification rules. Change keywords and negative signals to have the bot scan for different types of users.

After making changes to these files, commit and push them to your repository for the bot to use them in its next run.

## Monitoring Dashboard

The bot includes a local dashboard to monitor its status and view the current configuration.

1.  **Pull the latest changes** from your repository to ensure you have the most recent database file (`git pull origin main`).
2.  **Run the dashboard** with the command: `python3 -m src.main --dashboard`.
3.  **Open your browser** and navigate to `http://127.0.0.1:5000`.

## Disclaimer

This script is provided for educational and research purposes. Automating account actions may be against GitHub's Acceptable Use Policies. The author is not responsible for any consequences of using this bot, including but not limited to account suspension. Use this bot responsibly and at your own risk.
