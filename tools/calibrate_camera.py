#!/usr/bin/env python3
"""
相机标定 —— 4点法算出像素→世界坐标变换

使用方法:
  在工作台上放4个标记点(如红色圆形贴纸)，测量它们在实际桌面上的坐标(mm)
  然后运行此脚本，依次点击图像中的4个点
"""
import cv2, numpy as np, pickle, os

def calibrate(camera_id=0):
    # 实际坐标（需要你自己量！单位mm）
    print("=" * 50)
    print(" 相机标定 — 4点法")
    print("=" * 50)
    print()
    print("工作台上放4个标记点，量出它们的桌面坐标(mm):")
    world_points = []
    for i in range(4):
        x = float(input(f"  点{i+1} X(mm): "))
        y = float(input(f"  点{i+1} Y(mm): "))
        world_points.append([x, y])
    world_points = np.array(world_points, dtype=np.float32)

    # 拍照并点击
    cap = cv2.VideoCapture(camera_id)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("❌ 相机无法读取"); return

    image_points = []
    def click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            image_points.append([x, y])
            cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)
            cv2.imshow("click", frame)
            print(f"  已点 {len(image_points)}/4: ({x}, {y})")

    cv2.imshow("click", frame)
    cv2.setMouseCallback("click", click)
    print("\n依次点击图像中的4个标记点(必须与输入顺序一致!)")
    while len(image_points) < 4:
        cv2.waitKey(100)
    cv2.destroyAllWindows()

    image_points = np.array(image_points, dtype=np.float32)
    H, _ = cv2.findHomography(image_points, world_points)

    # 验证
    for i, (ip, wp) in enumerate(zip(image_points, world_points)):
        test = cv2.perspectiveTransform(np.array([[[ip[0], ip[1]]]], dtype=np.float32), H)
        print(f"  点{i+1}: 像素{ip} → 世界({test[0][0][0]:.1f},{test[0][0][1]:.1f})mm 实际{wp}mm")

    os.makedirs('config/calibration', exist_ok=True)
    path = 'config/calibration/camera_homography.pkl'
    with open(path, 'wb') as f:
        pickle.dump({'H': H, 'world_points': world_points, 'image_points': image_points}, f)
    print(f"\n标定结果已保存: {path}")
    print("更新 perception_node.py 加载此文件用于像素→世界转换")

if __name__ == '__main__':
    calibrate()
