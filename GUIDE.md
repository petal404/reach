# Deployment Guide for Project Reach

This guide provides a step-by-step process for deploying and running the `reach` bot using GitHub Actions.

---

### **Step 1: Generate a GitHub Personal Access Token (PAT)**

The bot needs a PAT to authenticate with the GitHub API on your behalf.

1.  **Navigate to GitHub's token page:** Go to [github.com/settings/tokens](https://github.com/settings/tokens).
2.  Click **"Generate new token"** and select **"Generate new token (classic)"**.
3.  **Name your token:** Give it a descriptive name, like `REACH_BOT_TOKEN`.
4.  **Set the expiration:** For long-term use, you can select "No expiration".
5.  **Select scopes:** You must grant the correct permissions. Check the box for **`user`**. This will automatically select all its sub-scopes (`read:user`, `user:email`, `user:follow`). This is the only scope needed.
6.  Click **"Generate token"** at the bottom of the page.
7.  **Copy the token immediately!** This is the only time you will see it. Store it in a safe place for the next step.

### **Step 2: Add the Token as a Repository Secret**

To use the token securely, you must add it to your repository's secrets. This keeps it out of the codebase.

1.  In your `reach` repository on GitHub, go to the **`Settings`** tab.
2.  In the left sidebar, navigate to **`Secrets and variables`** -> **`Actions`**.
3.  Click the **`New repository secret`** button.
4.  For the **`Name`**, you must enter exactly `REACH_BOT_TOKEN`.
5.  For the **`Secret`**, paste the Personal Access Token you copied in Step 1.
6.  Click **`Add secret`**.

### **Step 3: Customize the Bot's Behavior (Optional)**

You can fine-tune the bot's operation by editing the configuration files in the `config/` directory.

*   **`config/settings.yml`**: Adjust the `delays` between actions and the `limits` on how many users to process per run.
*   **`config/criteria.yml`**: Change the keywords and topics to target a different niche of users.

Commit and push any changes you make to these files to your repository.

### **Step 4: Enable and Run the Workflow**

The bot is run by a GitHub Actions workflow defined in `.github/workflows/bot_controller.yml`.

1.  Go to the **`Actions`** tab of your repository.
2.  In the left sidebar, you will see a workflow named **"Reach Bot Controller"**. Click on it.
3.  The workflow is scheduled to run automatically every 8 hours. However, you can trigger it manually.
4.  Click the **`Run workflow`** dropdown on the right side, and then click the green **`Run workflow`** button.

### **Step 5: Monitoring the Bot**

After a workflow run is complete, you can monitor its activity:

1.  **Workflow Logs:** Click on the specific workflow run in the `Actions` tab. You can view the complete log output from the bot, which will show which users were scanned, followed, or unfollowed.
2.  **State Commits:** The bot will automatically commit the `reach.db` (the database) and `reach.log` files to your repository after each run. This preserves the bot's memory. You can view the commit history to see when the bot has been active.

That's it! The bot is now deployed and will run on the schedule you've defined.
