## Author:  Owen Cocjin
## Version: 0.1
## Date:    2021.12.23
## Description:    Holds global resources
import threading

LOCK=threading.Lock()
thread_count=0
all_lists={"accept":[],
"close":[],
"drop":[],
"srverr":[]}

serv_err_unit=None  #Used by heartbeat
cli_err_unit=None  #Used by heartbeat

hb_event=threading.Event()