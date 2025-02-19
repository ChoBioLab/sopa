FROM nvcr.io/nvidia/cuda:12.4.0-devel-ubuntu22.04

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install the Python package
RUN pip3 install 'sopa[tangram]'

