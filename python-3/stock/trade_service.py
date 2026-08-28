import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath=os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
need_data=os.path.join(cpath_current, 'config','trade_client.json')
log_file=os.path.join(cpath_current, 'log','trade_client.log')
