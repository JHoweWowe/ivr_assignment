#!/usr/bin/env python3

import roslib
import sys
import rospy
import cv2
import numpy as np
from std_msgs.msg import String
from sensor_msgs.msg import Image
from std_msgs.msg import Float64MultiArray, Float64
from cv_bridge import CvBridge, CvBridgeError

from scipy.linalg import subspace_angles


class image_converter:

  # Defines publisher and subscriber
  def __init__(self):
    # initialize the node named image_processing
    rospy.init_node('image_processing', anonymous=True)

    # initialize a publisher to send images from camera1 to a topic named image_topic1
    self.image_pub1 = rospy.Publisher("image_topic1",Image, queue_size = 1)
    
    # initialize a subscriber to recieve messages from a topic named /robot/camera1/image_raw and use callback function to recieve data
    self.image_sub1 = rospy.Subscriber("/camera1/robot/image_raw",Image,self.callback1)
    self.image_sub1 = rospy.Subscriber("/camera2/robot/image_raw",Image,self.callback2)

    # initialize the bridge between openCV and ROS
    self.bridge = CvBridge()

    # ACTUAL movements: Publish actual joints states w.r.t sinusoidal signals
    self.joint2_pub = rospy.Publisher("/robot/joint2_position_controller/command",Float64,queue_size=10)
    self.joint3_pub = rospy.Publisher("/robot/joint3_position_controller/command",Float64,queue_size=10)
    self.joint4_pub = rospy.Publisher("/robot/joint4_position_controller/command",Float64,queue_size=10)

    # ESTIMATED movements: Publish estimated joint states 
    self.joint2_estimate_pub = rospy.Publisher("/robot/joint2_estimated_position",Float64,queue_size=10)
    self.joint3_estimate_pub = rospy.Publisher("/robot/joint3_estimated_position",Float64,queue_size=10)
    self.joint4_estimate_pub = rospy.Publisher("/robot/joint4_estimated_position",Float64,queue_size=10)
  
  def detect_red(self, image1, image2):
    red_mask_image1 = cv2.inRange(image1, (0,0,100), (35,35,255))
    M_image1 = cv2.moments(red_mask_image1)
    cy = int(M_image1['m10']/M_image1['m00'])
    cz = int(M_image1['m01']/M_image1['m00'])

    red_mask_image2 = cv2.inRange(image2, (0,0,100), (35,35,255))
    M_image2 = cv2.moments(red_mask_image2)
    cx = int(M_image2['m10']/M_image2['m00'])

    #print("Dimensions for red blob:")
    #print(np.array([cx,cy,cz]))

    return np.array([cx,cy,cz])

  def detect_blue(self, image1, image2):
    # Isolate blue color
    blue_mask_image1 = cv2.inRange(image1, (100,0,0), (255,50,50))

    # Obtain moments of binary image
    M_image1 = cv2.moments(blue_mask_image1)

    # Calculate pixel coordinates for blob center
    if (M_image1['m00'] != 0):
      cy = int(M_image1['m10']/M_image1['m00'])
      cz = int(M_image1['m01']/M_image1['m00'])
    else:
      cy = self.detect_yellow(image1, image2)[1]
      cz = self.detect_yellow(image1, image2)[2]

    blue_mask_image2 = cv2.inRange(image2, (100,0,0), (255,50,50))
    M_image2 = cv2.moments(blue_mask_image2)

    # Calculate pixel coordinates for blob center
    if (M_image2['m00'] != 0):
      cx = int(M_image2['m10']/M_image2['m00'])
      cz = int(M_image2['m01']/M_image2['m00'])
    else:
      cx = self.detect_yellow(image1,image2)[0]
      cz = self.detect_yellow(image1,image2)[2]

    #print("Dimensions for blue blob:")
    #print(np.array([cx,cy,cz]))

    cv2.circle(image1,(cy,cz), 3, (255,255,255), -1)
    cv2.circle(image2, (cx,cz), 3, (255,255,255), -1)

    return np.array([cx,cy,cz])
  
  def detect_green(self, image1, image2):
    # Isolate green color- threshold slightly differs!
    green_mask_image1 = cv2.inRange(image1, (0,100,0), (40,255,40))

    # Obtain moments of binary image
    M_image1 = cv2.moments(green_mask_image1)
    # Calculate pixel coordinates for blob center
    if (M_image1['m00'] != 0):
      cy = int(M_image1['m10']/M_image1['m00'])
      cz = int(M_image1['m01']/M_image1['m00'])
    else:
      cy = self.detect_blue(image1,image2)[1]
      cz = self.detect_blue(image1,image2)[2]

    green_mask_image2 = cv2.inRange(image2, (0,100,0), (40,255,40))

    # Currently problem with detecting moments centroid at green blob detection at camera 2
    contours, hierarchy = cv2.findContours(green_mask_image2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    M_image2 = cv2.moments(contours[0])
    if (M_image2['m00'] != 0):
      cx = int(M_image2['m10']/M_image2['m00'])
      cz = int(M_image2['m01']/M_image2['m00'])
    else:
      cx = self.detect_blue(image1,image2)[0]
      cz = self.detect_blue(image1,image2)[2]

    #print("Dimensions for green blob:")
    #print(np.array([cx,cy,cz]))

    #im1 = cv2.imshow('image2_green',green_mask_image2)
    cv2.circle(image1,(cy,cz), 2, (255,255,255), -1)
    cv2.circle(image2, (cx,cz), 2, (255,255,255), -1)

    return np.array([cx,cy,cz])

  # Testing purposes only
  def detect_yellow(self, image1, image2):
    yellow_mask_image1 = cv2.inRange(image1, (0,100,100), (35,255,255))
    M_image1 = cv2.moments(yellow_mask_image1)
    cy = int(M_image1['m10']/M_image1['m00'])
    cz = int(M_image1['m01']/M_image1['m00'])

    yellow_mask_image2 = cv2.inRange(image2, (0,100,100), (35,255,255))
    M_image2 = cv2.moments(yellow_mask_image2)
    cx = int(M_image2['m10']/M_image2['m00'])

    return np.array([cx,cy,cz])

  # Rotates link 2 based on X axis- use camera 1
  def pixel2MeterForLink2(self, image1, image2):
    joint2 = self.detect_blue(image1, image2)
    joint3 = self.detect_green(image1, image2)
    # Finds Pythagorean distance between two vectors
    dist = np.linalg.norm(joint3 - joint2)
    return 3.5 / dist

  # Rotates link 3 based on Y axis- will need to implement camera 2
  def pixel2MeterForLink3(self, image1, image2):
    joint2 = self.detect_blue(image1, image2)
    joint3 = self.detect_green(image1, image2)
    # Finds Pythagorean distance between two vectors
    dist = np.linalg.norm(joint3 - joint2)
    return 3.5 / dist

  # Rotates link 4 based on X axis- will need to use camera 1
  def pixel2MeterForLink4(self, image1, image2):
    joint3 = self.detect_green(image1, image2)
    joint4 = self.detect_red(image1, image2)
    # Pythagorean distance between two vectors
    dist = np.linalg.norm(joint4 - joint3)
    return 3 / dist

  # Joint angle 2
  def detect_joint_angle2(self, image1, image2):
    a = self.pixel2MeterForLink2(image1, image2)

    joint2 = a * self.detect_blue(image1, image2)
    joint3 = a * self.detect_green(image1, image2)

    directionVector = joint3 - joint2
    uDVector = directionVector / np.linalg.norm(directionVector)
    print("Unit Direction Vector")
    print(uDVector)

    uDVectorZAxis = np.array([0,0,-1])

    #myTestAngle = np.arccos((uDVectorZAxis[0] * uDVector[0] + uDVectorZAxis[1] * uDVector[1] + uDVectorZAxis[2] * uDVector[2]) / (np.sqrt(uDVectorZAxis[0]**2 + uDVectorZAxis[1]**2 + uDVectorZAxis[2]**2) * np.sqrt(uDVector[0]**2 + uDVector[1]**2 + uDVector[2]**2)))

    # Obtain X angle for YZ plane, and Y angle from XZ plane respectively- must consider positive and negative theta
    x_angle = np.arccos(uDVectorZAxis[1] * uDVector[1] + uDVectorZAxis[2] * uDVector[2])
    y_angle = np.arccos(uDVectorZAxis[0] * uDVector[0] + uDVectorZAxis[2] * uDVector[2])

    # If angle X rotates anti-clockwise (positive theta value)
    if (uDVector[1] <= 0):
      rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),(-1)*np.sin(x_angle)],[0,np.sin(x_angle),np.cos(x_angle)]])
      final_x_angle = np.arctan2(rotationMatrix_X[2][1],rotationMatrix_X[2][2])
    # If angle X rotates clockwise (negative theta value)
    elif (uDVector[1] > 0):
      rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),np.sin(x_angle)],[0,(-1)*np.sin(x_angle),np.cos(x_angle)]])
      final_x_angle = np.arctan2(rotationMatrix_X[2][1],rotationMatrix_X[2][2])

    return final_x_angle
    
    # # If angle X rotates anti-clockwise (positive theta value)
    # if (uDVector[0] >= 0 and uDVector[1] <= 0):
    #   rotation_matrix_Y = np.array([[np.cos(y_angle),0,np.sin(y_angle)],[0,1,0],[(-1)*np.sin(y_angle),0,np.cos(y_angle)]])
    #   rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),(-1)*np.sin(x_angle)],[0,np.sin(x_angle),np.cos(x_angle)]])
    #   rotationMatrix_X_Y = np.dot(rotationMatrix_X,rotation_matrix_Y)
    # elif (uDVector[0] >= 0 and uDVector[1] > 0):
    #   rotation_matrix_Y = np.array([[np.cos(y_angle),0,np.sin(y_angle)],[0,1,0],[(-1)*np.sin(y_angle),0,np.cos(y_angle)]])
    #   rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),np.sin(x_angle)],[0,(-1)*np.sin(x_angle),np.cos(x_angle)]])
    #   rotationMatrix_X_Y = np.dot(rotationMatrix_X,rotation_matrix_Y)
    # elif (uDVector[0] < 0 and uDVector[1] <= 0):
    #   rotation_matrix_Y = np.array([[np.cos(y_angle),0,(-1)*np.sin(y_angle)],[0,1,0],[np.sin(y_angle),0,np.cos(y_angle)]])
    #   rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),(-1)*np.sin(x_angle)],[0,np.sin(x_angle),np.cos(x_angle)]])
    #   rotationMatrix_X_Y = np.dot(rotationMatrix_X,rotation_matrix_Y)
    # elif (uDVector[0] < 0 and uDVector[1] > 0):
    #   rotation_matrix_Y = np.array([[np.cos(y_angle),0,(-1)*np.sin(y_angle)],[0,1,0],[np.sin(y_angle),0,np.cos(y_angle)]])
    #   rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),np.sin(x_angle)],[0,(-1)*np.sin(x_angle),np.cos(x_angle)]])
    #   rotationMatrix_X_Y = np.dot(rotationMatrix_X,rotation_matrix_Y)

    # final_angle = np.arctan2(rotationMatrix_X_Y[2][1],rotationMatrix_X_Y[2][2])
    #return final_angle

  # Joint angle 3
  def detect_joint_angle3(self, image1, image2):
    a = self.pixel2MeterForLink3(image1, image2)

    joint2 = a * self.detect_blue(image1, image2)
    joint3 = a * self.detect_green(image1, image2)

    directionVector = joint3 - joint2
    uDVector = directionVector / np.linalg.norm(directionVector)
    print("Unit Direction Vector for Y")
    print(uDVector)

    #angleY = (-1) * np.arcsin(-unitDirectionVector[0] / np.sqrt(1-(unitDirectionVector[1]**2)))

    uDVectorZAxis = np.array([0,0,-1])

    # Obtain X angle for YZ plane- must consider positive and negative theta
    x_angle = np.arccos(uDVectorZAxis[1] * uDVector[1] + uDVectorZAxis[2] * uDVector[2])
    
    # If angle X rotates anti-clockwise (positive theta value)
    if (uDVector[1] <= 0):
      rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),(-1)*np.sin(x_angle)],[0,np.sin(x_angle),np.cos(x_angle)]])
      final_x_angle = np.arctan2(rotationMatrix_X[2][1],rotationMatrix_X[2][2])
    # If angle X rotates clockwise (negative theta value)
    elif (uDVector[1] > 0):
      rotationMatrix_X = np.array([[1,0,0],[0,np.cos(x_angle),np.sin(x_angle)],[0,(-1)*np.sin(x_angle),np.cos(x_angle)]])
      final_x_angle = np.arctan2(rotationMatrix_X[2][1],rotationMatrix_X[2][2])

    # Obtain Y angle for XZ plane- must consider positive and negative theta
    y_angle = np.arccos(uDVectorZAxis[0] * uDVector[0] + uDVectorZAxis[2] * uDVector[2])
    if (uDVector[0] >= 0):
      rotation_matrix_Y = np.array([[np.cos(y_angle),0,np.sin(y_angle)],[0,1,0],[(-1)*np.sin(y_angle),0,np.cos(y_angle)]])
    elif (uDVector[0] < 0):
      rotation_matrix_Y = np.array([[np.cos(y_angle),0,(-1)*np.sin(y_angle)],[0,1,0],[np.sin(y_angle),0,np.cos(y_angle)]])
    
    final_y_angle = np.arctan2((-1)*rotation_matrix_Y[2][0],np.sqrt(rotation_matrix_Y[2][1]**2+rotation_matrix_Y[2][2]**2))

    return final_y_angle

  # Joint_angle 4 from camera 1 and 2
  def detect_joint_angle4(self, image1, image2):
    a = self.pixel2MeterForLink4(image1, image2)

    joint3 = a * self.detect_green(image1, image2)
    joint4 = a * self.detect_red(image1, image2)

    # Calculate direction vector wrt to difference between joint4 and joint3
    directionVector = joint4 - joint3
    unitDirectionVector = directionVector / np.linalg.norm(directionVector)

    angle = np.arcsin(unitDirectionVector[1])

    return angle

  # Recieve data from camera 1, process it, and publish
  def callback1(self,data):
    # Recieve the image
    try:
      self.cv_image1 = self.bridge.imgmsg_to_cv2(data, "bgr8")
    except CvBridgeError as e:
      print(e)
    
    # Uncomment if you want to save the image
    #cv2.imwrite('image_copy.png', cv_image)

    # Publish the results
    try: 
      self.image_pub1.publish(self.bridge.cv2_to_imgmsg(self.cv_image1, "bgr8"))

    except CvBridgeError as e:
      print(e)
  
  # Recieve data from camera 2, process it, and publish
  def callback2(self, data):
    # Recieve the image
    try:
      self.cv_image2 = self.bridge.imgmsg_to_cv2(data, "bgr8")
    except CvBridgeError as e:
      print(e)

    # ACTUAL VALUES
    # Set movement of joint values according to sinusoidal signals
    # and publish the movement values
    # Note: Joint 2 movement detection on its own works
    
    #joint2Value = Float64()
    #joint2Value.data = ((np.pi/2) * np.sin((np.pi/15) * rospy.get_time()))
    #joint2Value.data = -(np.pi/4)
    #self.joint2_pub.publish(joint2Value)

    joint3Value = Float64()
    joint3Value.data = ((np.pi/2) * np.sin((np.pi/18) * rospy.get_time()))
    #joint3Value.data = (np.pi/2)
    self.joint3_pub.publish(joint3Value)

    #joint4Value = Float64()
    #joint4Value.data = ((np.pi/2) * np.sin((np.pi/20) * rospy.get_time()))
    #self.joint4_pub.publish(joint4Value)
      
    # MY ESTIMATED VALUES
    # TO BE COMPLETED
    #joint2EstimatedValue = Float64()
    #joint2EstimatedValue.data = self.detect_joint_angle2(self.cv_image1, self.cv_image2)
    #self.joint2_estimate_pub.publish(joint2EstimatedValue)

    joint3EstimatedValue = Float64()
    joint3EstimatedValue.data = self.detect_joint_angle3(self.cv_image1, self.cv_image2)
    self.joint3_estimate_pub.publish(joint3EstimatedValue)
    
    # Differences between actual values and my values
    #print("Differences between Joint2 actual and estimated joint angle values:")
    #print(abs(joint2Value.data - joint2EstimatedValue.data))

    print("Differences between Joint3 actual and estimated joint angle values:")
    print(abs(joint3Value.data - joint3EstimatedValue.data))

    # Display images
    im1=cv2.imshow('window1', self.cv_image1)
    im2=cv2.imshow('window2', self.cv_image2)
    cv2.waitKey(1)

    # Publish the results
    try: 
      self.image_pub1.publish(self.bridge.cv2_to_imgmsg(self.cv_image2, "bgr8"))
    except CvBridgeError as e:
      print(e)

# call the class
def main(args):
  ic = image_converter()
  try:
    rospy.spin()
  except KeyboardInterrupt:
    print("Shutting down")
  cv2.destroyAllWindows()

# run the code if the node is called
if __name__ == '__main__':
    main(sys.argv)


