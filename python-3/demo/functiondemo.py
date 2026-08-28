def log_operation(operation, history=[]): 
    history.append(operation)
    return history
    
log_operation("登录")
log_operation("下单")