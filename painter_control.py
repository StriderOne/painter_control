import numpy as np
import pandas as pd
import os
import traceback
import time
import re
import pickle
import sys
import json
from  scipy.spatial.transform import Rotation
import UDriver as URDriver

class PainterControl():

    def __init__(self, ip, home_position, speed, acceleration, canfas_tf, verbose = False):
        self.__ip = ip
        self.__robot = URDriver.UniversalRobot(self.__ip)
        self.__robot_model = URDriver.robot.RobotModel('urdf_model/ur5e_right.urdf','world', 'tool0')
        self.verbose = verbose
        self.home_position = np.array(home_position) * np.pi / 180
        self.__speed = speed
        self.__acceleration = acceleration
        self.canvas_tf = canfas_tf

        if self.verbose:
            print(f"Create PainterControl with ip: {self.__ip}; home_position: {self.home_position}")
            print(f"Canvas transformation: {self.canvas_tf}")

        self.pose_above_canvas = self.calculate_pose_above_canvas(self.canvas_tf)
        

    def calculate_pose_above_canvas(self, canvas_tf, height_padding=0.0):
        rotation_pi = Rotation.from_euler('y', 180, degrees=True).as_matrix()
        rotvec = Rotation.from_matrix(canvas_tf[:3, :3] @ rotation_pi).as_rotvec()
        linear_pose = canvas_tf[:3, 3].copy()
        linear_pose[2] += height_padding
        pose = np.concatenate((linear_pose, rotvec))

        if self.verbose:
            print(f"Pose above canvas: {pose}")

        return pose

    def go_home(self):
        if self.verbose:
            print("Go to home postition!")
        self.__robot.control.servoStop()
        self.__robot.control.moveJ(self.home_position)

    def go_above_canvas(self):
        if self.verbose:
            print("Go to postition above canvas!")
        self.__robot.control.servoStop()
        self.__robot.control.moveL(self.pose_above_canvas, self.__speed, self.__acceleration)

    def reset_ft_sensor(self):
        if self.verbose:
            print("Reseting force sensor")
        time.sleep(1)
        self.__robot.control.zeroFtSensor()
        time.sleep(1)

    def get_force_in_tool_frame(self):
        self.__robot.update_state()
        force_at_world_frame = np.array(self.__robot.state.f).flatten()[:3]
        force_at_tool_frame = np.linalg.pinv(self.__robot_model.rot(self.__robot.state.q)) @ force_at_world_frame
        
        return force_at_tool_frame
        
    def move_until_contact(self, target_z_force):
        # Coefficients
        max_speed = 0.07
        
        vel = np.zeros(3)
        k_p = -0.005
        k_d = -0.00001
        err_f = 10
        prev_time = time.time()
        last_err = 0.0
        dt = 1.0/500
        while np.abs(err_f) > 0.1:
            start_time = time.time()
            delta_t = start_time - prev_time
            
            
            force = self.get_force_in_tool_frame()
            print(force)
            # error
            goal = target_z_force
            err_f = goal - force[2]
            derr_f = (err_f - last_err)/delta_t
            last_err = err_f

            # PID
            sum_f = k_p*err_f
            sum_f = sum_f if abs(sum_f) < max_speed else max_speed * np.sign(float(sum_f))
            sum_d = k_d*derr_f
        
            vel[0] = 0
            vel[1] = 0
            vel[2] = sum_f + sum_d

            print("vel_in_tool: ", vel)

            self.__robot.update_state()
            
            vel_in_base_frame = self.__robot_model.rot(self.__robot.state.q) @ vel

            print("vel_in_base: ", vel_in_base_frame)
            vel_in_base_frame = np.array([vel_in_base_frame[0], vel_in_base_frame[1], vel_in_base_frame[2], 0.0, 0.0, 0.0])
            self.__robot.control.speedL(vel_in_base_frame, 0.5, dt)

            end_time = time.time()
            prev_time = start_time
            duration = end_time - start_time
            if duration < dt:
                time.sleep(dt - duration)

    def draw_canvas_axis(self, axes:str):
        
        painter_control.reset_ft_sensor()
        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()
        x = 0
        y = 0
        z = 0
        start_pose = (self.canvas_tf @ np.array([x, y, z, 1.0]))[:3] # pose on canvas in world
        start_pose = np.concatenate((start_pose, current_pose[3:]))
        
        print('start_pose', start_pose)
        self.__robot.control.moveL(start_pose, self.__speed, self.__acceleration, False)
        
        self.move_until_contact(-4)

        self.__robot.control.speedStop()

        if is_x:
            x = 0.03
        else:
            y = 0.03

        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()
        rotation = self.__robot_model.rot(self.__robot.state.q)
        tf_world2ee = np.array([
            [rotation[0][0], rotation[0][1], rotation[0][2], current_pose[0]],
            [rotation[1][0], rotation[1][1], rotation[1][2], current_pose[1]],
            [rotation[2][0], rotation[2][1], rotation[2][2], current_pose[2]],
            [0.0, 0.0, 0.0, 1.0]
        ])
        height = (np.linalg.pinv(tf_world2ee) @ self.canvas_tf)[2, 3]
        print("height: ", np.linalg.pinv(tf_world2ee) @ self.canvas_tf)
        pose = (self.canvas_tf @ np.array([x, y, z, 1.0]))[:3]
        print("FIRST POSE: ", pose)
        pose_in_tool_frame =  np.linalg.pinv(tf_world2ee) @ np.array([pose[0], pose[1], pose[2], 1.0]) 
        pose_in_tool_frame[2] = 0.0
        pose_in_world = tf_world2ee @ np.array([pose_in_tool_frame[0], pose_in_tool_frame[1], pose_in_tool_frame[2], 1.0])
        print("pose_in_tool_frame: ", pose_in_tool_frame)
        print("pose_in_world: ", pose_in_world)
        start_pose = np.concatenate((pose_in_world[:3], current_pose[3:]))
        
        # print('start_pose', start_pose)
        self.__robot.control.moveL(start_pose, self.__speed, self.__acceleration, False)

    def make_spline(self, spline):
        
        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()
        z = 0
        x = spline[0][0]
        y = spline[0][1]
        # print(x, y)
        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()
        rotation = self.__robot_model.rot(self.__robot.state.q)
        tf_world2ee = np.array([
            [rotation[0][0], rotation[0][1], rotation[0][2], current_pose[0]],
            [rotation[1][0], rotation[1][1], rotation[1][2], current_pose[1]],
            [rotation[2][0], rotation[2][1], rotation[2][2], current_pose[2]],
            [0.0, 0.0, 0.0, 1.0]
        ])
        height = (np.linalg.pinv(tf_world2ee) @ self.canvas_tf)[2, 3]
        print("height: ", np.linalg.pinv(tf_world2ee) @ self.canvas_tf)
        pose = (self.canvas_tf @ np.array([x, y, z, 1.0]))[:3]
        print("FIRST POSE: ", pose)
        pose_in_tool_frame =  np.linalg.pinv(tf_world2ee) @ np.array([pose[0], pose[1], pose[2], 1.0]) 
        pose_in_tool_frame[2] = 0.0
        pose_in_world = tf_world2ee @ np.array([pose_in_tool_frame[0], pose_in_tool_frame[1], pose_in_tool_frame[2], 1.0])
        print("pose_in_tool_frame: ", pose_in_tool_frame)
        print("pose_in_world: ", pose_in_world)
        start_pose = np.concatenate((pose_in_world[:3], current_pose[3:]))
        
        # print('start_pose', start_pose)
        self.__robot.control.moveL(start_pose, self.__speed, self.__acceleration, False)
        # return
        self.move_until_contact(-4)

        self.__robot.control.speedStop()
        dt = 1.0/500
        
        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()
        z = current_pose[2]

        for q in spline:
            start = time.time()
            self.__robot.update_state()
            current_pose = self.__robot.receive.getActualTCPPose()

            x = q[0] 
            y = q[1] 
            z = 0

            self.__robot.update_state()
            current_pose = self.__robot.receive.getActualTCPPose()
            rotation = self.__robot_model.rot(self.__robot.state.q)
            tf_world2ee = np.array([
                [rotation[0][0], rotation[0][1], rotation[0][2], current_pose[0]],
                [rotation[1][0], rotation[1][1], rotation[1][2], current_pose[1]],
                [rotation[2][0], rotation[2][1], rotation[2][2], current_pose[2]],
                [0.0, 0.0, 0.0, 1.0]
            ])
            height = (np.linalg.pinv(tf_world2ee) @ self.canvas_tf)[2, 3]
            print("height: ", np.linalg.pinv(tf_world2ee) @ self.canvas_tf)
            pose = (self.canvas_tf @ np.array([x, y, z, 1.0]))[:3]
            print("FIRST POSE: ", pose)
            pose_in_tool_frame =  np.linalg.pinv(tf_world2ee) @ np.array([pose[0], pose[1], pose[2], 1.0]) 
            pose_in_tool_frame[2] = 0.0
            pose_in_world = tf_world2ee @ np.array([pose_in_tool_frame[0], pose_in_tool_frame[1], pose_in_tool_frame[2], 1.0])
            print("pose_in_tool_frame: ", pose_in_tool_frame)
            print("pose_in_world: ", pose_in_world)
            pose = np.concatenate((pose_in_world[:3], current_pose[3:]))
            
            # print('start_pose', start_pose)

            self.__robot.control.servoL(pose, 0.01, 0.5, dt, 0.1, 300)
            last_q = q
            end = time.time()
            duration = end - start
            if duration < dt:
                time.sleep(dt - duration)


        self.__robot.control.servoStop()
        
        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()

        x = q[0] 
        y = q[1] 
        z = 0

        self.__robot.update_state()
        current_pose = self.__robot.receive.getActualTCPPose()
        rotation = self.__robot_model.rot(self.__robot.state.q)
        tf_world2ee = np.array([
            [rotation[0][0], rotation[0][1], rotation[0][2], current_pose[0]],
            [rotation[1][0], rotation[1][1], rotation[1][2], current_pose[1]],
            [rotation[2][0], rotation[2][1], rotation[2][2], current_pose[2]],
            [0.0, 0.0, 0.0, 1.0]
        ])
        height = (np.linalg.pinv(tf_world2ee) @ self.canvas_tf)[2, 3]
        print("height: ", np.linalg.pinv(tf_world2ee) @ self.canvas_tf)
        pose = (self.canvas_tf @ np.array([x, y, z, 1.0]))[:3]
        print("FIRST POSE: ", pose)
        pose_in_tool_frame =  np.linalg.pinv(tf_world2ee) @ np.array([pose[0], pose[1], pose[2], 1.0]) 
        pose_in_tool_frame[2] = -0.02
        pose_in_world = tf_world2ee @ np.array([pose_in_tool_frame[0], pose_in_tool_frame[1], pose_in_tool_frame[2], 1.0])
        print("pose_in_tool_frame: ", pose_in_tool_frame)
        print("pose_in_world: ", pose_in_world)
        pose = np.concatenate((pose_in_world[:3], current_pose[3:]))

        self.__robot.control.moveL(pose, self.__speed, self.__acceleration, False)


    def drawing(self, pickle_file, one_color=False):
        self.reset_ft_sensor()
        if self.verbose:
            print("Load pickle...")

        data = pickle.load(pickle_file)

        trajectories = data['trajectories']
        color_num = trajectories[0]['color']
        trajectories_count = len(data['trajectories'])

        for i, trajectory in enumerate(trajectories):
            
            trajectory_color = trajectory['color']
            self.__robot.control.zeroFtSensor()
            
            if (not one_color and trajectory_color <= 0):
                continue
            
            trajectory_points = trajectory['points']
            
            # change color
            if (abs(color_num - trajectory_color) > 0):
                
                self.go_above_canvas()
                
                self.go_home()
                if self.verbose:
                    print(f"Finish splines with color {color_num}, preparing for next color...")
                input('Press enter to continue:')
                color_num = trajectory_color

                self.go_above_canvas()

            if self.verbose:
                print('[i / truajectories]: {}/{}'.format(i, trajectories_count))
            
            self.make_spline(trajectory_points)





if __name__ == '__main__':
    config_file = open('config.json')
    config = json.load(config_file)
    
    painter_control = PainterControl(ip = config["ip"], home_position = config["home_position"], speed = config["speed"], acceleration = config["acceleration"], verbose=True)

    painter_control.go_home()
    time.sleep(1)
    painter_control.go_above_canvas()
    # time.sleep(1)
    # painter_control.reset_ft_sensor()
    # painter_control.move_until_contact(-10.0)
    directory = './pickles/'
    filename = directory + 'trjs_bridge.pickle'
    # STAGE = 0
    with open(filename, 'rb') as file:
        painter_control.drawing(file, one_color=True)
    # painter_control.draw_canvas_axis(is_x = True)
    # painter_control.go_above_canvas()
    # painter_control.draw_canvas_axis(is_x = False)
    # painter_control.go_above_canvas()
    
    

