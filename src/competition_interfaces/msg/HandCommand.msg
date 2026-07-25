# Hand control command
# Published to /hand/command topic to control the hand
int16[6] target_angles   # target angles (-1 means "don't move this finger")
int16[6] force_thresholds # force control thresholds (unit: g, 0-1000 four fingers, 0-1200 thumb)
int16[6] speeds          # movement speed (0-4000, 2000≈1000ms full stroke)
int16[6] modes           # 0=speed-force-protect 1=force-closed-loop 2=impedance
