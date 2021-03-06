import requests
from bitcoinrpc.authproxy import AuthServiceProxy
import discord
import asyncio
import time
import re
import random
import sys
import traceback
from math import isclose
import os

# If you do not have this, obtain one by following https://discordpy.readthedocs.io/en/latest/discord.html (no permissions required)
# Do not share this with anyone!
BOT_TOKEN = os.environ["PANDA_AUDIT_TOKEN"]
# This is the currency which you received API key for
CURRENCY_TICKER = os.environ["PANDA_CURRENCY"] # eg. BOO
# Run $stakeonode to retrieve the API key, you must be admin of the project
FAT_PANDA_CLUB_API_KEY = os.environ["PANDA_API_KEY"]
# This is the panda-bot audit channel for logging all transactions
PANDA_AUDIT_CHANNEL = os.environ["PANDA_AUDIT_CHANNEL"]
# This is the backup audit channel, only used on error
BACKUP_AUDIT_CHANNEL = os.environ["PANDA_BACKUP_CHANNEL"]
# IP of target node, 127.0.0.1 for localhost
TIP_NODE_HOST = os.environ["PANDA_TIP_HOST"]
# Port of stake node
TIP_NODE_PORT = os.environ["PANDA_TIP_PORT"]
# Provide RPC credentials
TIP_NODE_RPC_USERNAME = os.environ["PANDA_TIP_USERNAME"]
TIP_NODE_RPC_PASSWORD = os.environ["PANDA_TIP_PASSWORD"]

### This example file is provided for basic blockchain based currencies, 
### other virtual currencies can utilize their own methods for deposit detection and withdrawal processing

AUDIT_MESSAGE_REGEX = r"^\[\ ([a-z0-9]{1,7}\-\d+)\ \].*\ (?:withdrawn|staked)\ ([0-9]+\.[0-9]+?)\ via.*\ to\ ([a-zA-Z0-9_]+?)\!$"

client = discord.Client()

@client.event
async def on_error(event, *args, **kwargs):
    await client.close()
    sys.exit("Discord Error")
    
@client.event
async def on_ready():
    # Randomize start time, do not remove or you will be rate limited!
    sleep_time = random.randint(1, 299)
    print("Sleeping for %s seconds..." % sleep_time)
    await asyncio.sleep(sleep_time)

    headers = {
        'x-api-key': FAT_PANDA_CLUB_API_KEY,
        'content-type': "application/json",
        'user-agent': "panda-tip-node-%s" % CURRENCY_TICKER.lower()
        }

    # On failure check VPS is able to access target node and RPC credentials are correct
    connection = AuthServiceProxy("http://%s:%s@%s:%s" % \
        ( TIP_NODE_RPC_USERNAME, TIP_NODE_RPC_PASSWORD, TIP_NODE_HOST, TIP_NODE_PORT) , timeout=10)

    # Customize based on individual daemon
    try:
        current_balance = connection.getbalance()
        recent_transactions = connection.listtransactions("*", 100, 0)
    except Exception as exception:
        print("Could not connect to daemon: %s" % exception)
        await client.close()
        sys.exit(exception)

    transactions_to_submit = {}
    api_submission = False
    api_request = False

    for tx in recent_transactions:
        if tx['category'] != "receive":
            continue
        if tx['confirmations'] < 2:
            continue
        if 'generated' in tx and tx['generated']:
            continue
        if not 'vout' in tx:
            raw_tx = connection.getrawtransaction(tx['txid'])
            decoded_tx = connection.decoderawtransaction(raw_tx)
            vout = "x"
            for vo in decoded_tx['vout']:
                if tx['address'] in vo['scriptPubKey']['addresses']:
                    vout = vo['n']
                    break
        else:
            vout = tx['vout']
        flag_conflicts = False
        if 'walletconflicts' in tx and len(tx['walletconflicts']) > 0:
            flag_conflicts = True
        transactions_to_submit[tx['txid']] = {
                'conflicts': flag_conflicts,
                'address': tx['address'],
                'amount': float(tx['amount']),
                'vout': int(vout),
                'time': int(tx['time']) # Use 'timereceived' or 'blocktime' if 'time' not available
            } 

    # Submit deposits to panda-bot
    print("Submitting %s deposit tx" % len(transactions_to_submit))
    url = "https://api.fatpanda.club/wallet/%s" % CURRENCY_TICKER.lower()
    payload = {
        "op": "deposit",
        "transactions": transactions_to_submit,
        "timestamp": int(time.time()),
        'balance': float(current_balance),
    }
    response = requests.request("POST", url, headers=headers, json=payload)
    if response.status_code == 200:
        api_submission = True
        response_json = response.json()
        panda_audit_channel = client.get_channel(int(PANDA_AUDIT_CHANNEL))
        project_audit_channel = client.get_channel(response_json['private_audit_channel'])

        print(response_json)
        for accepted in response_json['accepted_deposit']:
            deposit_message = "%0.3f [ %s ] deposit accepted, txid: `%s`" % (transactions_to_submit[accepted]['amount'], response_json['ticker'], accepted)
            try:
                await panda_audit_channel.send(content=deposit_message)
                await project_audit_channel.send(content=deposit_message)
            except Exception as exception:
                print("Could not send deposit audit messages due to: %s" % exception)

    elif response.status_code == 429:
        await client.close()
        sys.exit("Rate limited! Please decrease your job frequency and wait a while.")
    else:
        api_submission_error = response.json()['message']

    # Process operations from panda-bot
    response = requests.request("GET", url, headers=headers)
    if response.status_code != 200:
        print("Could not GET wallet ops")
        print(response.text)
        api_request_error = response.json()['message']
    elif response.status_code == 429:
        await client.close()
        sys.exit("Rate limited! Please decrease your job frequency and wait a while.")
    else:
        print("Obained wallet ops")
        print(response.text)
        api_request = True
        withdraw_ops = response.json()['withdraw']
        address_ops = response.json()['address']
        panda_audit_channel = client.get_channel(int(PANDA_AUDIT_CHANNEL))
        project_audit_channel = client.get_channel(int(response.json()['private_audit_channel']))

        for op in address_ops:
            new_address = connection.getnewaddress()
            address_message = "Generated new address `%s` for user %s from %s" % (new_address, op['requested_by'], op['platform'])
            op['new_address'] = new_address
            response = requests.request("POST", url, headers=headers, json=op)
            try:
                await panda_audit_channel.send(content=address_message)
                await project_audit_channel.send(content=address_message)
            except Exception as exception:
                print("Could not send address audit messages due to: %s" % exception)
        for op in withdraw_ops:
            # Make sure audit messages are correct, for both panda and project
            ### DO NOT CHANGE THIS! This is under project accountability
            project_audit_message = await project_audit_channel.fetch_message(op['private_audit_id'])
            project_audit_validation = re.match(AUDIT_MESSAGE_REGEX, project_audit_message.content.strip())
            panda_audit_message = await panda_audit_channel.fetch_message(op['panda_audit_id'])
            panda_audit_validation = re.match(AUDIT_MESSAGE_REGEX , panda_audit_message.content.strip())

            if not project_audit_validation:
                withdraw_message = "[ %s-%s ] project audit validation failed!" % (op['currency'], op['reference'])

            elif not project_audit_validation.group(1).lower() == "%s-%s" % (CURRENCY_TICKER.lower(), op['reference'].lower()):
                withdraw_message = "[ %s-%s ] project ticker validation failed!" % (op['currency'], op['reference'])

            elif not isclose(float(project_audit_validation.group(2)), op['amount'] + op['fee'], abs_tol=1e-5):

                withdraw_message = "[ %s-%s ] project amount validation failed!\n%0.4f vs %0.4f + %0.4f" % (op['currency'], op['reference'], float(project_audit_validation.group(2)), op['amount'], op['fee'] )

            elif not project_audit_validation.group(3).lower() == op['to_address'].lower():
                withdraw_message = "[ %s-%s ] project address validation failed!" % (op['currency'], op['reference'])

            elif not panda_audit_validation:
                withdraw_message = "[ %s-%s ] panda audit validation failed!" % (op['currency'], op['reference'])

            elif not panda_audit_validation.group(1).lower() == "%s-%s" % (CURRENCY_TICKER.lower(), op['reference'].lower()):
                withdraw_message = "[ %s-%s ] panda ticker validation failed!" % (op['currency'], op['reference'])

            elif not isclose(float(panda_audit_validation.group(2)), op['amount'] + op['fee'], abs_tol=1e-5):
                withdraw_message = "[ %s-%s ] panda amount validation failed!\n%0.4f vs %0.4f + %0.4f" % (op['currency'], op['reference'], float(panda_audit_validation.group(2)), op['amount'], op['fee'] )

            elif not panda_audit_validation.group(3).lower() == op['to_address'].lower():
                withdraw_message = "[ %s-%s ] panda address validation failed!" % (op['currency'], op['reference'])

            else:
                ### ALL CHECKS PERFORMED TO ENSURE AUDIT MESSAGES ARE VALID, ELSE TX IS SKIPPED and NOT PROCESSED
                try:
                    txid = connection.sendtoaddress(op['to_address'], op['amount'])
                    withdraw_message = "[ %s-%s ] withdrawal sent: %s" % (op['currency'], op['reference'], txid)
                except Exception as exception:
                    txid = 'failed'
                    withdraw_message = "[ %s-%s ] withdrawal failed! %s" % (op['currency'], op['reference'], exception)
            try:
                await panda_audit_channel.send(content=withdraw_message)
                await project_audit_channel.send(content=withdraw_message)
            except Exception as exception:
                print("Could not send withdraw audit messages due to: %s" % exception)

            op['txid'] = txid
            response = requests.request("POST", url, headers=headers, json=op)

    try:
        if int(BACKUP_AUDIT_CHANNEL) != 0:
            audit_channel = client.get_channel(int(BACKUP_AUDIT_CHANNEL))
            if not api_submission:
                await audit_channel.send(content="API submission to panda-bot has failed due to: %s" % api_submission_error)
            if not api_request:
                await audit_channel.send(content="API request to panda-bot has failed due to: %s" % api_request_error)

    except Exception as exception:
        print("Could not send audit error messages due to: %s" % exception)

    await client.close()

client.run(BOT_TOKEN)

