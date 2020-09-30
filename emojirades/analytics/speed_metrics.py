# Speed metrics, simple and weighted

import json
import pandas as pd
from datetime import datetime, timedelta

# Reading in the history

sc = pd.read_json('scores.json')
scores = pd.json_normalize(sc["C7Q5Z7M26"]["history"])

# Calc function

def speed_iter(in_bnd, day_num):
    pos_sc = in_bnd[in_bnd['operation'] == '++'].groupby(['user_id','operation'], as_index = False).count()
    neg_sc = in_bnd[in_bnd['operation'] == '--'].groupby(['user_id','operation'], as_index = False).count()

    pos_sc = pos_sc.rename(columns = {'timestamp':'pos_score'})
    neg_sc = neg_sc.rename(columns = {'timestamp':'neg_score'})

    scores = pd.merge(left = pos_sc,
                      right = neg_sc,
                      how = 'left',
                      on= 'user_id').fillna(0)

    scores['score'] = scores['pos_score'] - scores['neg_score']
    scores = scores[scores['score'] > 0]
    scores['speed'] = scores['score'] / day_num
    sp = scores[['user_id', 'speed']]
    return sp

# Simple speed, average over the last 4 weeks
def sim_speed(scores):
    # getting the 4 weeks from the latest timestamp
    dt_bnd = scores['timestamp'][len(scores)-1]-4*7*24*60*60

    scores_4wk = scores[(scores['timestamp'] >= dt_bnd)] 

    ssp = speed_iter(scores_4wk,28)
    
    return ssp

# Weighted speed over the last 6 weeks

def weight_speed(scores):

    # getting the timing markers
    bnd1 = scores['timestamp'][len(scores)-1]-2*7*24*60*60
    bnd2 = scores['timestamp'][len(scores)-1]-4*7*24*60*60
    bnd3 = scores['timestamp'][len(scores)-1]-6*7*24*60*60

    s_bnd1 = scores[(scores['timestamp'] >= bnd1)] 
    s_bnd2 = scores[(scores['timestamp'] < bnd1) & (scores['timestamp'] >= bnd2)] 
    s_bnd3 = scores[(scores['timestamp'] < bnd2) & (scores['timestamp'] >= bnd3)] 

    # Only doing 10 days rather than the 14 as games are rare on the weekend.
    
    s1 = speed_iter(s_bnd1, 10)
    s2 = speed_iter(s_bnd2, 10)
    s3 = speed_iter(s_bnd3, 10)

    s1 = s1.rename(columns = {'speed':'speed1'})
    s2 = s2.rename(columns = {'speed':'speed2'})
    s3 = s3.rename(columns = {'speed':'speed3'})

    w_s = pd.merge(left = s1,
                   right = s2,
                   how = 'outer',
                   on= 'user_id')

    w_s = pd.merge(left = w_s,
                   right = s3,
                   how = 'outer',
                   on= 'user_id').fillna(0)

    # Here is the weighting. 4,2,1 for the 3 brackets of timings.
    w_s['w_speed'] = (4*w_s['speed1'] + 2*w_s['speed2'] + 1*w_s['speed3']) / 7

    w_s = w_s[['user_id','w_speed']]
    
    return w_s
