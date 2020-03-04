# our base image
FROM continuumio/miniconda3

# update essential packages
RUN apt update && \
    apt -y install bzip2 curl gcc ssh rsync git vim cron && \
    apt-get clean

# creating our conda environment
ARG CONDA_ENV_FILE
ARG CONDA_PATH="/root/miniconda3/bin"
ARG CONDA_BIN="$CONDA_PATH/conda"
COPY $CONDA_ENV_FILE $CONDA_ENV_FILE

ENV SHELL /bin/bash
RUN conda install nb_conda
ENV PATH /root/miniconda3/envs/stock_screener/bin:$CONDA_PATH:$PATH

# update the environment
COPY conda.yml .
RUN conda env update -n stock_screener --file ./conda.yml

# adding our environment variables for Cron job to work
RUN printenv >> /etc/environment

# allow log messages to be printed in interactive terminal
ENV PYTHONUNBUFFERED 1

# run shell script
RUN chmod +x ./run.sh
ENTRYPOINT ["./run.sh"]