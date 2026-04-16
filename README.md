# Urbex Factory Bot

A modern, highly-aesthetic, and fully custom Discord bot created expressly for The Urbex Factory. 

Built entirely around the newest Discord V2 UI components (discord.py 2.7.1+), this bot provides completely seamless in-client functionality natively managing the community's economy, verification submissions, and reward redemptions.

## Features

* Native V2 Submission Systems:
  Users can submit comprehensive location reviews and updates directly inside the Discord UI using interactive Modals. The bot validates uploads and instantly generates a highly-polished native V2 MediaGallery for server staff to review in one click.
* Persistent Economy Tracker:
  A built-in SQLite engine tracks user Coins, XP, Level, and overall Leaderboard standing silently and reliably across interactions without third-party dependencies.
* Shop Integration:
  Custom logic allowing members with sufficient economy coins to open automated "Shop Claims". 
* Booster Rewards:
  Tracks Server Boosters and rewards them automatically upon initial boost and across monthly recurring booster milestones.
* Robust Admin Panel:
  All server customization variables are manageable safely through the in-client `/bot_setup_guide` dashboard. Change reward values, lock panels to channels natively, and update settings immediately.

## Setup & Deployment Guide

This section will walk you through setting up and running the Urbex Factory Bot locally or on a VPS.

### 1. Prerequisites
- Python 3.11+: The bot heavily relies on typing and features from recent Python versions.
- Discord Bot Token: Create an application on the Discord Developer Portal.
- Intents: In the Developer Portal under the "Bot" tab, ensure that all three Privileged Gateway Intents (Presence, Server Members, Message Content) are checked.

### 2. Installation
1. Clone this repository or move the UrbexBot folder to your host environment.
2. Open a terminal inside the bot's root directory.
3. Install the dependencies by running:
   `pip install -r requirements.txt`

### 3. Configuration
The bot uses a `.env` file to securely store credentials. 
1. Copy the `.env.example` file and rename the copy to `.env`.
2. Open `.env` and fill in your Bot Token and Owner ID.
   `BOT_TOKEN=your_token_here`
   `OWNER_ID=your_discord_id_here`

### 4. Running the Bot
Once everything is configured, run the following command to start the bot:
`python main.py`
Note: Upon its first run, the bot will automatically generate and initialize the `urbexbot.db` or `database.db` file required for economy tracking and submissions.

### 5. First-Time Setup in Discord
Once the bot is online and invited to your server:
1. Make sure you have the Administrator permission in the server.
2. Type `/bot_setup_guide` in any channel to view the setup dashboard.
3. Use `/setup_logs` to automatically generate a private admin category and logging channels.
4. Configure the Admin Approvals channel. This binds the bot's sensitive output, like pending review approval logs, to a private channel.
5. Set up the specific reward values for Daily bonuses, Review approvals, Updates, and Boosting.
6. Setup the UI Forms Channels (Reviews and Updates) to automatically configure read-only tracking and the sticky submission panels.

### 6. Updating the Bot
If you add new commands to the bot or modify slash commands, remember that the Bot automatically syncs them on startup via the setup hook. You do not need to manually force sync unless actively developing logic trees.
