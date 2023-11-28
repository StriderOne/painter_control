ARG BASE_IMG='ubuntu:22.04'

FROM ${BASE_IMG}
SHELL ["/bin/bash", "-ci"]

# Timezone Configuration
ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    git vim curl nano tmux curl wget lsb-release \
    net-tools build-essential gcc g++ \
    cmake clang make \
    gnupg2 ca-certificates software-properties-common \
    libboost-dev libeigen3-dev libcppunit-dev \
    python3 python3-dev libpython3-dev python3-pip \
    python3-distutils python3-psutil python3-future \
    freeglut3-dev mesa-utils libusb-1.0-0-dev libopencv-dev libcanberra-gtk-module && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install opencv-python cython pandas scipy ur-rtde spatialmath-python urdf-parser-py
RUN pip3 install -i https://test.pypi.org/simple/ UDriver

WORKDIR /workspace

RUN git clone --branch v1.5.1 https://github.com/orocos/orocos_kinematics_dynamics.git && \
    cd orocos_kinematics_dynamics && git submodule update --init && \
    cd /workspace/orocos_kinematics_dynamics/orocos_kdl && mkdir build && cd build && \
    cmake .. && make && make install && \
    cd /workspace/orocos_kinematics_dynamics/python_orocos_kdl && mkdir build && cd build && \
    cmake .. && make && make install && \
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib && \
    echo "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib" >> ~/.bashrc && \
    ldconfig


WORKDIR /workspace/painter_reborn
COPY . /workspace/painter_reborn
ENV LD_LIBRARY_PATH=/usr/local/lib

