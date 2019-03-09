import csv
from datetime import datetime
from os import path

from database import DATA_DIR
from utils import l

def get_log_file(guild, name):
    return path.join(DATA_DIR, f'{name}_log_{guild.id}.csv')

def append_to_log(guild, name, data_values):
    with open(get_log_file(guild, name), 'a+') as f:
        csv.writer(f).writerow(data_values)


def add_to_vote_log(guild, *,
                    timestamp=None,
                    vote_type,
                    agent_id,
                    user_id,
                    proposal_number,
                    vote_count=1,
                    reason=''):
    """Add an entry to the vote log.

    Vote log format:
    <timestamp> for     <agent_id>  <user_id>   <proposal_number> <vote_count>  [reason ...]
    <timestamp> against <agent_id>  <user_id>   <proposal_number> <vote_count>  [reason ...]
    <timestamp> abstain <agent_id>  <user_id>   <proposal_number> <vote_count>  [reason ...]
    <timestamp> remove  <agent_id>  <user_id>   <proposal_number> <vote_count>  [reason ...]
    """
    append_to_log(guild, 'vote', [
        int((timestamp or datetime.utcnow()).timestamp()),
        vote_type,
        agent_id or user_id,
        user_id,
        proposal_number,
        vote_count,
        reason.strip(),
    ])


def add_to_proposal_log(guild, *,
                        timestamp=None,
                        event_name,
                        user_id,
                        proposal_number,
                        new_number=None,
                        reason=''):
    """Add an entry to the proposal log.

    Proposal log format:
    <timestamp> submit      <user_id>   <proposal_number>   [reason ...]
    <timestamp> remove      <user_id>   <proposal_number>   [reason ...]
    <timestamp> renumber    <user_id>   <proposal_number>   <new_number>
    <timestamp> set_passed  <user_id>   <proposal_number>   [reason ...]
    <timestamp> set_failed  <user_id>   <proposal_number>   [reason ...]
    <timestamp> set_voting  <user_id>   <proposal_number>   [reason ...]
    """
    append_to_log(guild, 'proposal', [
        int((timestamp or datetime.utcnow()).timestamp()),
        event_name,
        user_id,
        proposal_number,
        new_number or reason.strip(),
    ])


def add_to_transaction_log(guild, *,
                           timestamp=None,
                           currency,
                           agent_id,
                           recipient_id,
                           amt,
                           reason=''):
    """Add an entry to the transaction log.

    Transaction log format:
    <timestamp> <currency>  <agent_id>  <recipient_id>  +<amt>  [reason ...]
    <timestamp> <currency>  <agent_id>  <recipient_id>  -<amt>  [reason ...]
    """
    append_to_log(guild, 'transaction', [
        int((timestamp or datetime.utcnow()).timestamp()),
        currency,
        agent_id or recipient_id,
        recipient_id,
        amt,
        reason.strip(),
    ])
