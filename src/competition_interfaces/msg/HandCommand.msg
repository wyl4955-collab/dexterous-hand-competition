# Hand control command — subscribed by rh56f2_driver
int16[6] target_angles     # 0.1-degree (-1 = don't move this finger)
int16[6] force_thresholds  # grams (0-1000 four fingers, 0-1200 thumb)
int16[6] speeds            # 0-4000 (2000 ≈ 1000ms full stroke)
int16[6] modes             # 0=speed_force_protect 1=force_closed_loop 2=impedance
