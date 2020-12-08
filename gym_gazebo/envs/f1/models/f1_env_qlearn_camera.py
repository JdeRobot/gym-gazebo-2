import rospy
import numpy as np
import cv2

from cv_bridge import CvBridge

from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image


from gym_gazebo.envs.f1.modes.f1_env import GazeboF1Env

from gym.utils import seeding
from agents.f1.settings import actions
from agents.f1.settings import telemetry, x_row, center_image, width, height, telemetry_mask, max_distance

from image_f1 import *


class F1QlearnCameraEnv(GazeboF1Env):

    def __init__(self):
        GazeboF1Env.__init__(self)
        self.image = ImageF1()

    def render(self, mode='human'):
        pass

    @staticmethod
    def all_same(items):
        return all(x == items[0] for x in items)

    def image_msg_to_image(self, img, cv_image):

        self.image.width = img.width
        self.image.height = img.height
        self.image.format = "RGB8"
        self.image.timeStamp = img.header.stamp.secs + (img.header.stamp.nsecs * 1e-9)
        self.image.data = cv_image

        return self.image

    @staticmethod
    def get_center(lines):

        try:
            point = np.divide(np.max(np.nonzero(lines)) - np.min(np.nonzero(lines)), 2)
            point = np.min(np.nonzero(lines)) + point
        except:
            point = 9

        return point

    @staticmethod
    def calculate_reward(error):

        d = np.true_divide(error, center_image)
        reward = np.round(np.exp(-d), 4)

        return reward

    def processed_image(self, img):
        """
        Convert img to HSV. Get the image processed. Get 3 lines from the image.

        :parameters: input image 640x480
        :return: x, y, z: 3 coordinates
        """

        img_sliced = img[240:]
        img_proc = cv2.cvtColor(img_sliced, cv2.COLOR_BGR2HSV)
        line_pre_proc = cv2.inRange(img_proc, (0, 30, 30), (0, 255, 255))  # default: 0, 30, 30 - 0, 255, 200
        # gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(line_pre_proc, 240, 255, cv2.THRESH_BINARY)

        lines = [mask[x_row[idx], :] for idx, x in enumerate(x_row)]
        centrals = list(map(self.get_center, lines))

        # if centrals[-1] == 9:
        #     centrals[-1] = center_image

        if telemetry_mask:
            mask_points = np.zeros((height, width), dtype=np.uint8)
            for idx, point in enumerate(centrals):
                # mask_points[x_row[idx], centrals[idx]] = 255
                cv2.line(mask_points, (point, x_row[idx]), (point, x_row[idx]), (255, 255, 255), thickness=3)

            cv2.imshow("MASK", mask_points[240:])
            cv2.waitKey(3)

        return centrals

    @staticmethod
    def calculate_observation(state):

        normalize = 40

        final_state = []
        for _, x in enumerate(state):
            final_state.append(int((center_image - x) / normalize) + 1)

        return final_state

    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    @staticmethod
    def show_telemetry(img, points, action, reward):
        count = 0
        for idx, point in enumerate(points):
            cv2.line(img, (320, x_row[idx]), (320, x_row[idx]), (255, 255, 0), thickness=5)
            # cv2.line(img, (center_image, x_row[idx]), (point, x_row[idx]), (255, 255, 255), thickness=2)
            cv2.putText(img, str("err{}: {}".format(idx+1, center_image - point)), (18, 340 + count), font, 0.4,
                        (255, 255, 255), 1)
            count += 20
        cv2.putText(img, str("action: {}".format(action)), (18, 280), font, 0.4, (255, 255, 255), 1)
        cv2.putText(img, str("reward: {}".format(reward)), (18, 320), font, 0.4, (255, 255, 255), 1)

        cv2.imshow("Image window", img[240:])
        cv2.waitKey(3)

    def step(self, action):

        self._gazebo_unpause()

        vel_cmd = Twist()
        vel_cmd.linear.x = actions[action][0]
        vel_cmd.angular.z = actions[action][1]
        self.vel_pub.publish(vel_cmd)

        # Get camera info
        image_data = None
        f1_image_camera = None
        while image_data is None:
            image_data = rospy.wait_for_message('/F1ROS/cameraL/image_raw', Image, timeout=5)
            # Transform the image data from ROS to CVMat
            cv_image = CvBridge().imgmsg_to_cv2(image_data, "bgr8")
            f1_image_camera = self.image_msg_to_image(image_data, cv_image)
        # image_data = rospy.wait_for_message('/F1ROS/cameraL/image_raw', Image, timeout=1)
        # cv_image = CvBridge().imgmsg_to_cv2(image_data, "bgr8")
        # f1_image_camera = self.image_msg_to_image(image_data, cv_image)

        self._gazebo_pause()

        points = self.processed_image(f1_image_camera.data)
        state = self.calculate_observation(points)

        center = float(center_image - points[0]) / (float(width) // 2)

        done = False
        center = abs(center)

        if center > 0.9:
            done = True
        if not done:
            if 0 <= center <= 0.2:
                reward = 10
            elif 0.2 < center <= 0.4:
                reward = 2
            else:
                reward = 1
        else:
            reward = -100

        if telemetry:
            print(f"center: {center} - actions: {action} - reward: {reward}")
            # self.show_telemetry(f1_image_camera.data, points, action, reward)

        return state, reward, done, {}

    def reset(self):
        # === POSE ===
        if self.circuit["alternate_pose"]:
            self.set_new_pose()
        else:
            self._gazebo_reset()

        self._gazebo_unpause()

        # Get camera info
        image_data = None
        f1_image_camera = None
        success = False
        while image_data is None or success is False:
            image_data = rospy.wait_for_message('/F1ROS/cameraL/image_raw', Image, timeout=5)
            cv_image = CvBridge().imgmsg_to_cv2(image_data, "bgr8")
            f1_image_camera = self.image_msg_to_image(image_data, cv_image)
            if f1_image_camera:
                success = True

        points = self.processed_image(f1_image_camera.data)
        state = self.calculate_observation(points)
        # reset_state = (state, False)

        self._gazebo_pause()

        return state

    def inference(self, action):
        self._gazebo_unpause()

        vel_cmd = Twist()
        vel_cmd.linear.x = actions[action][0]
        vel_cmd.angular.z = actions[action][1]
        self.vel_pub.publish(vel_cmd)

        image_data = rospy.wait_for_message('/F1ROS/cameraL/image_raw', Image, timeout=1)
        cv_image = CvBridge().imgmsg_to_cv2(image_data, "bgr8")
        f1_image_camera = self.image_msg_to_image(image_data, cv_image)

        self._gazebo_pause()

        points = self.processed_image(f1_image_camera.data)
        state = self.calculate_observation(points)

        center = float(center_image - points[0]) / (float(width) // 2)

        done = False
        center = abs(center)

        if center > 0.9:
            done = True

        return state, done

    def finish_line(self):
        x, y = self.get_position()
        current_point = np.array([x, y])

        dist = (self.start_pose - current_point) ** 2
        dist = np.sum(dist, axis=0)
        dist = np.sqrt(dist)
        # print(dist)
        if dist < max_distance:
            return True
        return False