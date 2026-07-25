# Hand joint state (6 DoF for RH56F2)
# Published at 50Hz by rh56f2_driver
float32[6] angles        # current angles (unit: 0.1 deg, 900-1740 four fingers, 1100-1550 thumb bend, 600-1750 thumb rotate)
float32[6] forces        # current fingertip forces (unit: g)
float32[6] currents      # motor currents (unit: mA)
int16[6]   status        # 0=releasing 1=grasping 2=position_stop 3=force_stop 5=current_protect 6=stall 7=fault 8=estop
int16[6]   faults        # bit0=stall bit1=overtemp bit2=overcurrent bit3=motor_error bit4=comm_error
int16[6]   temperatures  # motor temperature (unit: Celsius)
