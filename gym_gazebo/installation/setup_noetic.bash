#!/bin/bash

DIR="../CustomRobots"
if ! [[ -d "$DIR" ]]
then
    echo "$DIR doesn't exists. Cloning CustomRobots repository."
    git clone --branch noetic-devel https://github.com/JdeRobot/CustomRobots.git $DIR
else
    echo "CustomRobots is already downloaded. Pass."
fi

if [ -z "$ROS_DISTRO" ]; then
  echo "ROS not installed. Check the installation steps: https://github.com/erlerobot/gym#installing-the-gazebo-environment"
fi

program="gazebo"
condition=$(which $program 2>/dev/null | grep -v "not found" | wc -l)
if [ $condition -eq 0 ] ; then
    echo "Gazebo is not installed. Check the installation steps: https://github.com/erlerobot/gym#installing-the-gazebo-environment"
fi

source /opt/ros/noetic/setup.bash

# ----- Create catkin_ws -----------------------------------
ws="catkin_ws"
if [ -d $ws ]; then
  echo "Error: catkin_ws directory already exists" 1>&2
fi
src=$ws"/src"
mkdir -p $src
cd $src
catkin_init_workspace

# Import and build dependencies
cd ../../catkin_ws/src/
vcs import < ../../gazebo_ros_noetic.repos

cd ..
touch catkin_ws/src/ecl_navigation/ecl_mobile_robot/CATKIN_IGNORE
catkin_make
bash -c 'echo source `pwd`/devel/setup.bash >> ~/.bashrc'

echo "## ROS workspace compiled ##"
# ---------------------------------

# Add own models path to gazebo models path
if [ -z "$GAZEBO_MODEL_PATH" ]; then
  bash -c 'echo "export GAZEBO_MODEL_PATH="`pwd`/../CustomRobots/f1/models >> ~/.bashrc'
else
  printf "GAZEBO_MODEL_PATH env variable already exists in your .bashrc."
fi

# ZSH config
# read -p "Do you use zsh? [Y/n]: " zsh
# if [ "${!zsh}" = "" ]; then
  # bash -c 'echo "export GAZEBO_MODEL_PATH="`pwd`/../CustomRobots/f1/models >> ~/.zshrc'
  # zsh -c 'echo source `pwd`/devel/setup.bash >> ~/.zshrc'
  # source $HOME/.zshrc
  
# fi

printf ""
printf "\nRestarting the terminal...\n"
exec bash
