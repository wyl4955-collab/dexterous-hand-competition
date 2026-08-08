#!/usr/bin/env python3
"""Capture synchronised colour + depth frames for offline calibration.

Supports both competition tasks: bean-picking and powder-weighing.

Usage (on Orin — the robot's vision computer)::

    source install/setup.bash

    # Bean-picking task:
    python3 scripts/collect_data.py --task bean --output data/bean_calib

    # Powder-weighing task:
    python3 scripts/collect_data.py --task powder --output data/powder_calib

    # Both tasks in one session:
    python3 scripts/collect_data.py --task all --output data/calib

How it works:
    The script shows you the live camera feed.  You arrange the table for a
    specific scene (e.g. "empty source bowl + 5 beans"), then press Enter to
    save one frame.  The script guides you through every scene you need to
    collect — it tells you what to put on the table next.

    Collected files per frame:
        frame_NNNN_timestamp_color.png        colour image (BGR, 1280x720)
        frame_NNNN_timestamp_depth.npy        depth image (uint16, mm)
        frame_NNNN_timestamp_camera_info.npz  camera intrinsics (K, D)
        frame_NNNN_timestamp_note.txt         your note for this frame
"""

import argparse
import os
import sys
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from cv_bridge import CvBridge

# ===========================================================================
# Data-collection checklists for each task.
# Each entry is (scene_label, description_of_what_to_put_on_the_table).
# ===========================================================================

BEAN_SCENES = [
    # --- calibration markers ---
    ("calib_markers", "Place 4 known-position markers on the table (coins/chess pieces at measured coordinates). These are for homography calibration."),
    # --- empty containers ---
    ("empty_both", "Empty source bowl + empty target bowl. No beans. No tweezers."),
    ("empty_source", "Empty source bowl only. Target bowl removed from table."),
    # --- beans (varying counts) ---
    ("beans_1", "Source bowl with exactly 1 soybean. Place it near the centre."),
    ("beans_5", "Source bowl with 5 soybeans, randomly spread."),
    ("beans_10", "Source bowl with 10 soybeans."),
    ("beans_20", "Source bowl with 20 soybeans (crowded, some touching)."),
    # --- edge cases ---
    ("beans_edge", "Source bowl with 5 beans, at least 2 placed very close to the bowl wall."),
    ("beans_clumped", "Source bowl with 10 beans, several touching / clumped together."),
    # --- tweezers ---
    ("tweezers_alone", "Tweezers placed flat in their designated pickup zone. No bowls, no beans."),
    ("tweezers_full", "Full competition layout: source bowl + target bowl + tweezers in zone + 10 beans."),
    # --- lighting variations ---
    ("light_bright", "Full layout. Brighter lighting if adjustable (e.g. extra lamp)."),
    ("light_dim", "Full layout. Dimmer lighting (e.g. curtains drawn, lamp off)."),
    # --- extra: different bowl colours (if bowls change between rounds) ---
    ("alt_bowls", "If available: alternative bowl colours/materials. Otherwise skip (press Enter without changing anything)."),
]

POWDER_SCENES = [
    # --- calibration markers ---
    ("calib_markers", "Place 4 known-position markers on the table. Same as bean task — these are for homography calibration."),
    # --- empty table ---
    ("empty_all", "Completely empty table. No powder, no spoons, no scale."),
    # --- powder container ---
    ("powder_container_empty", "Powder container, empty, on the left side."),
    ("powder_container_full", "Powder container, filled with powder, on the left side."),
    ("powder_container_half", "Powder container, about half-full."),
    # --- spoons ---
    ("spoons_all", "All spoons placed in the spoon zone (right side). Arrange them spread apart so they don't overlap in the camera view."),
    ("spoons_large_only", "Only the large spoon in the spoon zone."),
    ("spoons_medium_only", "Only the medium spoon in the spoon zone."),
    ("spoons_small_only", "Only the small spoon in the spoon zone."),
    ("spoons_overlapping", "Spoons placed overlapping (worst-case scenario — tests if detector handles occlusion)."),
    # --- electronic scale ---
    ("scale_powered_off", "Electronic scale in centre position, powered OFF."),
    ("scale_zero", "Scale powered ON, showing 0.0 g."),
    ("scale_reading_01", "Scale showing a reading — place a small weight to get ~10-15 g."),
    ("scale_reading_02", "Scale showing a different reading — add/remove weight to get ~30-40 g."),
    ("scale_reading_03", "Scale showing a third reading — aim for ~50-60 g."),
    ("scale_reading_04", "Scale with decimal value (e.g. 12.3 g, 47.8 g). Place an irregular-weight object."),
    # --- full layout ---
    ("powder_full_01", "Full layout: powder container (left) + scale (centre, showing ~25g) + all spoons (right)."),
    ("powder_full_02", "Full layout with different scale reading (~50g)."),
    # --- lighting ---
    ("light_bright", "Full layout under brighter light."),
    ("light_dim", "Full layout under dimmer light."),
    # --- alternatives ---
    ("alt_containers", "If using different container colours/materials, swap and collect."),
]


# ===========================================================================
class FrameGrabber(Node):
    """Minimal ROS2 node that caches the latest colour + depth + camera_info."""

    def __init__(self):
        super().__init__('frame_grabber')
        self.bridge = CvBridge()
        self._color: np.ndarray | None = None
        self._depth: np.ndarray | None = None
        self._info: CameraInfo | None = None

        self.color_sub = self.create_subscription(
            Image, '/ob_camera_head/color/image_raw',
            self._cb_color, 10,
        )
        self.depth_sub = self.create_subscription(
            Image, '/ob_camera_head/depth/image_raw',
            self._cb_depth, 10,
        )
        self.info_sub = self.create_subscription(
            CameraInfo, '/ob_camera_head/color/camera_info',
            self._cb_info, 10,
        )

    def _cb_color(self, msg: Image):
        try:
            self._color = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception:
            pass

    def _cb_depth(self, msg: Image):
        try:
            self._depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono16')
        except Exception:
            pass

    def _cb_info(self, msg: CameraInfo):
        self._info = msg

    def grab(self) -> tuple[np.ndarray | None, np.ndarray | None, CameraInfo | None]:
        rclpy.spin_once(self, timeout_sec=1.0)
        return self._color, self._depth, self._info


# ===========================================================================
def run_collection(output_dir: str, scenes: list[tuple[str, str]], task_name: str):
    """Run the interactive collection loop for one task's scene list."""

    rclpy.init()
    grabber = FrameGrabber()

    task_dir = os.path.join(output_dir, task_name)
    os.makedirs(task_dir, exist_ok=True)

    # ---- print checklist so the user can prepare before starting ----------
    print()
    print("=" * 70)
    print(f"  TASK: {task_name}")
    print(f"  SAVING TO: {task_dir}/")
    print("=" * 70)
    print()
    print("SCENE CHECKLIST (you'll go through these one by one):")
    print("-" * 70)
    for i, (label, desc) in enumerate(scenes):
        print(f"  {i + 1:2d}. [{label}]")
        print(f"      {desc}")
    print("-" * 70)
    print()
    print("HOW TO USE:")
    print("  1. Read the prompt for the current scene.")
    print("  2. Arrange the items on the table as described.")
    print("  3. Press ENTER to save a frame.")
    print("  4. Repeat — you can take multiple shots per scene by pressing ENTER again.")
    print("  5. Type 's' + ENTER to skip to the next scene.")
    print("  6. Type 'q' + ENTER to quit at any time.")
    print()
    print("The camera feed is NOT shown on screen (you're on a remote terminal).")
    print("Take 2-3 shots per scene for safety (press ENTER 2-3 times).")
    print()

    input("Press ENTER to begin the first scene...")

    count = 0
    scene_index = 0

    try:
        while rclpy.ok() and scene_index < len(scenes):
            label, desc = scenes[scene_index]
            print()
            print(f"[SCENE {scene_index + 1}/{len(scenes)}] {label}")
            print(f"  → {desc}")
            print(f"  → Arrange the table, then press ENTER to snap (s=skip, q=quit)")
            print()

            shots_this_scene = 0

            while True:
                # Spin until we have at least a colour image.
                color = None
                for _ in range(10):
                    color, depth, info = grabber.grab()
                    if color is not None:
                        break

                if color is None:
                    print("  (waiting for camera image...)")
                    continue

                # Build a short status line.
                parts = [f"color {color.shape[1]}x{color.shape[0]}"]
                if depth is not None:
                    parts.append(f"depth {depth.shape[1]}x{depth.shape[0]}")
                if info is not None:
                    parts.append("info ✓")

                summary_dir = task_dir.replace(os.path.expanduser("~"), "~")
                print(f"  [{', '.join(parts)}]  →  Ready.  ", end="", flush=True)

                line = sys.stdin.readline().strip().lower()

                if line == 'q':
                    print("\n  Quit requested.")
                    return count

                if line == 's':
                    print(f"\n  Skipping to next scene. ({shots_this_scene} shots taken)")
                    break

                # ENTER (empty line) or any other key → save.
                ts = time.strftime('%Y%m%d_%H%M%S')
                prefix = os.path.join(task_dir, f"{label}_{count:04d}_{ts}")

                if color is not None:
                    cv2.imwrite(f'{prefix}_color.png', color)
                if depth is not None:
                    np.save(f'{prefix}_depth.npy', depth)
                if info is not None:
                    k = np.array(info.k).reshape(3, 3)
                    d = np.array(info.d)
                    np.savez(f'{prefix}_camera_info.npz', K=k, D=d,
                             width=info.width, height=info.height)
                # Write a small note file so you remember what this frame was.
                with open(f'{prefix}_note.txt', 'w', encoding='utf-8') as f:
                    f.write(f"task: {task_name}\n")
                    f.write(f"scene: {label}\n")
                    f.write(f"description: {desc}\n")
                    f.write(f"shot_number_in_scene: {shots_this_scene + 1}\n")
                    f.write(f"timestamp: {ts}\n")

                count += 1
                shots_this_scene += 1
                print(f"  ✓ saved #{count} ({shots_this_scene} in this scene)")

            scene_index += 1

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    finally:
        grabber.destroy_node()
        rclpy.shutdown()
        print(f"\nDone. {count} frames saved to {task_dir}/")
        return count


# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='Collect calibration images for bean-picking and/or powder-weighing tasks.',
    )
    parser.add_argument(
        '--task', choices=['bean', 'powder', 'all'], default='bean',
        help='Which competition task to collect data for (default: bean).',
    )
    parser.add_argument(
        '--output', default='data/calib',
        help='Output directory (will create task subdirectories inside).',
    )
    args = parser.parse_args()

    total = 0

    if args.task in ('bean', 'all'):
        total += run_collection(args.output, BEAN_SCENES, 'bean')

    if args.task in ('powder', 'all'):
        total += run_collection(args.output, POWDER_SCENES, 'powder')

    print()
    print("=" * 70)
    print(f"  ALL DONE.  {total} total frames saved to {args.output}/")
    print("=" * 70)
    print()
    print("NEXT STEP: copy the data to your local computer for offline calibration.")
    print()
    print("  From your Windows PowerShell (not WSL, not SSH):")
    print(f"    scp -r ubuntu@192.168.41.2:~/dexterous-hand-competition/{args.output} .")
    print()
    print("  Or if you collected on the x86:")
    print(f"    scp -r ubuntu@192.168.41.1:~/dexterous-hand-competition/{args.output} .")
    print()


if __name__ == '__main__':
    main()
