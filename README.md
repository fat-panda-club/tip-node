# tip-node

Requires python3.7+

## Create a bot user to communicate with panda-bot

```
Creating a Bot account is a pretty straightforward process.

Make sure you’re logged on to the [Discord website](https://discord.com/)

Navigate to the [application page](https://discord.com/developers/applications)

Click on the “New Application” button.

Give the application a name and click “Create”. Note down the Client ID.

Create a Bot User by navigating to the “Bot” tab and clicking “Add Bot”.

Click “Yes, do it!” to continue.

Note down the Bot Token by clicking the "Copy" button. (Never share this)

Invite the bot to your server by using this link, replace <CLIENT_ID> with what you recorded earlier:
https://discordapp.com/oauth2/authorize?client_id=<CLIENT_ID>&scope=bot&permissions=0

```

Instructions are taken from https://discordpy.readthedocs.io/en/latest/discord.html 

## Retrieve API key from panda-bot

Run $tipnode command in DM or any channel with panda-bot present, you will need to provide the Bot user CLIENT_ID


## Git clone and update script

```
cd ~
git clone https://github.com/fat-panda-club/tip-node.git
cd tip-node
python3 -m pip install -r requirements.txt
vi panda_tip_node.py
```

Insert values as follows:

| Attribute  | Description |
| ------------- | ------------- |
| BOT_TOKEN | The token you have retrieved in the first step
| CURRENCY_TICKER  | The ticker of your currency registered on panda-bot  |
| FAT_PANDA_CLUB_API_KEY  | panda-bot API key which you can obtain with $tipnode  |
| TIP_NODE_HOST | IP of the live node |
| TIP_NODE_PORT | Port number of the live node |
| TIP_NODE_RPC_USERNAME | RPC User of the live node |
| TIP_NODE_RPC_PASSWORD | RPC Password of the live node |


The RPC settings are generally set in the daemon config similarly to below:

```
rpcuser=user
rpcpassword=pass
rpcport=123
rpcallowip=1.2.3.4/32 

```
This IP is the host/VM which will be running the tip-node script

## Create crontask 

Trigger every 5 minutes, replace with path to python3 and script location where applicable

`*/5 * * * * /usr/bin/python3 ~/tip-node/panda_tip_node.py >> ~/panda_tip_node.log 2>&1`


## Set up tip node 

Set up your blockchain node on the same or an alternate VPS with the configuration from above steps
Keep this node updated and DO NOT make transactions manually

## Notes

The script will communicate panda-bot API on average every 5 minutes, please do not increase the frequency as it will be rejected
If you'd like assistance with setting up please [contact us via Discord](https://discord.gg/Hs57Jg4) 

## Disclaimer

Ensure your project is properly set up with an available audit channel on Discord that both your bot user and panda-bot can access.

All blockchain transactions are recorded and validated from both project and panda-bot side to avoid potential tampering. Message editing or deletion is recorded by additonal tooling in the Fat Panda Club channel.

The code provided here have been tested and is fully functional as long as the tip node is in sync, it will the be project team's responsibility to ensure the node is maintained and the log (~/panda_tip_node.log) reviewed regularly for anomalies.

