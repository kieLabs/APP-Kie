FROM gradle:9.8-jdk17-noble

USER root
ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:$PATH \
    APK_KIE_DATA_DIR=/data/apk-kie \
    GRADLE_USER_HOME=/home/gradle/.gradle

RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${ANDROID_HOME}/cmdline-tools ${APK_KIE_DATA_DIR} \
    && curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip -o /tmp/android-cmdline-tools.zip \
    && unzip -q /tmp/android-cmdline-tools.zip -d ${ANDROID_HOME}/cmdline-tools \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm /tmp/android-cmdline-tools.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"

WORKDIR /srv/apk-kie
COPY requirements.txt ./requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --upgrade pip && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PATH=/opt/venv/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
