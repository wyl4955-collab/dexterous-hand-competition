# 6-DoF hand state — published at 50Hz by rh56f2_driver
float32[6] angles        # 0.1-degree units (900-1740 four fingers, 1100-1550 thumb bend, 600-1750 thumb rotate)
float32[6] forces        # grams
float32[6] currents      # mA
int16[6] status          # 0=release 1=grasping 2=position_stop 3=force_stop 5=current 6=stall 7=fault 8=estop
int16[6] faults          # bit0=stall bit1=overtemp bit2=overcurrent bit3=motor bit4=comm
int16[6] temperatures    # Celsius
