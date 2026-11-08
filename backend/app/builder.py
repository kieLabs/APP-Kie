from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .models import BuildConfig

ProgressCallback = Callable[[int, str, str], None]


def _java_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _xml(value: str) -> str:
    return escape(value, {'"': '&quot;', "'": '&apos;'})


def _safe_project_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", value.title()) or "WebsiteApp"
    if cleaned[0].isdigit():
        cleaned = "App" + cleaned
    return cleaned[:35]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_icon(source: Path | None, res_dir: Path, app_name: str, splash_color: str) -> None:
    sizes = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    base = Image.new("RGB", (512, 512), splash_color)
    draw = ImageDraw.Draw(base)
    if source and source.exists():
        with Image.open(source) as original:
            original = ImageOps.exif_transpose(original).convert("RGBA")
            original.thumbnail((420, 420), Image.Resampling.LANCZOS)
            icon = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            x = (512 - original.width) // 2
            y = (512 - original.height) // 2
            icon.alpha_composite(original, (x, y))
            base = Image.alpha_composite(base.convert("RGBA"), icon).convert("RGB")
    else:
        draw.rounded_rectangle((55, 55, 457, 457), radius=104, fill="#ffffff")
        letter = (app_name.strip()[:1] or "A").upper()
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 230)
        except OSError:
            font = ImageFont.load_default(size=220)
        box = draw.textbbox((0, 0), letter, font=font)
        x = (512 - (box[2] - box[0])) / 2 - box[0]
        y = (512 - (box[3] - box[1])) / 2 - box[1] - 10
        draw.text((x, y), letter, fill=splash_color, font=font)

    for density, size in sizes.items():
        target = res_dir / f"mipmap-{density}" / "ic_launcher.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        base.resize((size, size), Image.Resampling.LANCZOS).save(target, "PNG", optimize=True)

    # Adaptive launcher icon foreground; background color is defined in colors.xml.
    foreground = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
    resized = base.convert("RGBA")
    resized.thumbnail((360, 360), Image.Resampling.LANCZOS)
    foreground.alpha_composite(resized, ((432 - resized.width) // 2, (432 - resized.height) // 2))
    fg_path = res_dir / "drawable" / "ic_launcher_foreground.png"
    fg_path.parent.mkdir(parents=True, exist_ok=True)
    foreground.save(fg_path, "PNG", optimize=True)


def _manifest(config: BuildConfig) -> str:
    permissions = ["<uses-permission android:name=\"android.permission.INTERNET\" />"]
    features = []
    if config.camera_enabled:
        permissions.append('<uses-permission android:name="android.permission.CAMERA" />')
        features.append('<uses-feature android:name="android.hardware.camera" android:required="false" />')
    if config.microphone_enabled:
        permissions.append('<uses-permission android:name="android.permission.RECORD_AUDIO" />')
        features.append('<uses-feature android:name="android.hardware.microphone" android:required="false" />')
    orientation = {
        "portrait": "portrait",
        "landscape": "landscape",
        "unspecified": "unspecified",
    }[config.orientation]
    return f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    {''.join(permissions)}
    {''.join(features)}
    <application
        android:allowBackup="false"
        android:label="{_xml(config.app_name)}"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher"
        android:usesCleartextTraffic="false"
        android:supportsRtl="true"
        android:theme="@style/SplashTheme">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="{orientation}"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'''


def _main_activity(config: BuildConfig, package_name: str) -> str:
    start_url = _java_string(config.site_url)
    origin = _java_string(config.site_url)
    return f'''package {package_name};

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {{
    private static final String START_URL = {start_url};
    private static final String START_HOST_URL = {origin};
    private static final boolean JS_ENABLED = {str(config.javascript_enabled).lower()};
    private static final boolean STORAGE_ENABLED = {str(config.dom_storage_enabled).lower()};
    private static final boolean FILE_UPLOAD_ENABLED = {str(config.file_upload_enabled).lower()};
    private static final boolean CAMERA_ENABLED = {str(config.camera_enabled).lower()};
    private static final boolean MICROPHONE_ENABLED = {str(config.microphone_enabled).lower()};
    private static final boolean FULLSCREEN_ENABLED = {str(config.fullscreen_enabled).lower()};
    private static final boolean EXTERNAL_LINKS_IN_APP = {str(config.allow_external_links).lower()};

    private WebView webView;
    private ProgressBar progressBar;
    private ValueCallback<Uri[]> fileChooserCallback;
    private PermissionRequest pendingPermissionRequest;
    private String[] pendingWebResources;
    private static final int FILE_CHOOSER_REQUEST = 4101;
    private static final int WEB_PERMISSION_REQUEST = 4102;

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        setTheme(R.style.AppTheme);
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        int statusColor = Color.parseColor("{config.status_bar_color}");
        int navigationColor = Color.parseColor("{config.navigation_bar_color}");
        window.setStatusBarColor(statusColor);
        window.setNavigationBarColor(navigationColor);
        int systemUi = 0;
        if (isLightColor(statusColor)) systemUi |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (isLightColor(navigationColor)) systemUi |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        window.getDecorView().setSystemUiVisibility(systemUi);
        if (Build.VERSION.SDK_INT >= 35) {{
            // Android 15/16 enforce edge-to-edge for apps targeting API 35/36.
            window.setStatusBarColor(Color.TRANSPARENT);
            window.setNavigationBarColor(Color.TRANSPARENT);
        }}
        if (FULLSCREEN_ENABLED) {{
            window.getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }}

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);
        View topSystemBar = new View(this);
        topSystemBar.setBackgroundColor(statusColor);
        root.addView(topSystemBar, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0));
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setProgress(0);
        root.addView(progressBar, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(3)));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);
        root.addView(webView, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        View bottomSystemBar = new View(this);
        bottomSystemBar.setBackgroundColor(navigationColor);
        root.addView(bottomSystemBar, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0));
        if (Build.VERSION.SDK_INT >= 35) {{
            root.setOnApplyWindowInsetsListener((view, insets) -> {{
                int top = insets.getInsets(WindowInsets.Type.statusBars()).top;
                int bottom = insets.getInsets(WindowInsets.Type.navigationBars()).bottom;
                LinearLayout.LayoutParams topParams = (LinearLayout.LayoutParams) topSystemBar.getLayoutParams();
                topParams.height = FULLSCREEN_ENABLED ? 0 : top;
                topSystemBar.setLayoutParams(topParams);
                LinearLayout.LayoutParams bottomParams = (LinearLayout.LayoutParams) bottomSystemBar.getLayoutParams();
                bottomParams.height = FULLSCREEN_ENABLED ? 0 : bottom;
                bottomSystemBar.setLayoutParams(bottomParams);
                return insets;
            }});
        }}
        setContentView(root);
        if ({str(config.keep_screen_on).lower()}) {{
            getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }}

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(JS_ENABLED);
        settings.setDomStorageEnabled(STORAGE_ENABLED);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setGeolocationEnabled(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {{
            settings.setSafeBrowsingEnabled(true);
        }}
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        webView.setWebViewClient(new WebViewClient() {{
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {{
                return handleUrl(request.getUrl().toString());
            }}
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {{
                return handleUrl(url);
            }}
        }});
        webView.setWebChromeClient(new WebChromeClient() {{
            @Override
            public void onProgressChanged(WebView view, int newProgress) {{
                progressBar.setProgress(newProgress);
                progressBar.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }}
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {{
                if (!FILE_UPLOAD_ENABLED) return false;
                if (fileChooserCallback != null) fileChooserCallback.onReceiveValue(null);
                fileChooserCallback = callback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                try {{ startActivityForResult(Intent.createChooser(intent, "Select file"), FILE_CHOOSER_REQUEST); }}
                catch (Exception error) {{ fileChooserCallback = null; return false; }}
                return true;
            }}
            @Override
            public void onPermissionRequest(PermissionRequest request) {{
                runOnUiThread(() -> handleWebPermission(request));
            }}
        }});
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {{
            try {{ startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }} catch (Exception ignored) {{ }}
        }});
        webView.loadUrl(START_URL);
    }}

    private int dp(int value) {{ return (int) (value * getResources().getDisplayMetrics().density + 0.5f); }}

    private boolean isLightColor(int color) {{
        double luminance = (0.299 * Color.red(color) + 0.587 * Color.green(color) + 0.114 * Color.blue(color)) / 255.0;
        return luminance > 0.72;
    }}

    private boolean handleUrl(String url) {{
        Uri uri = Uri.parse(url);
        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase();
        if (scheme.equals("tel") || scheme.equals("mailto") || scheme.equals("sms") || scheme.equals("intent")) {{
            try {{ startActivity(new Intent(Intent.ACTION_VIEW, uri)); }} catch (Exception ignored) {{ }}
            return true;
        }}
        if (!scheme.equals("https") && !scheme.equals("http")) return true;
        if (!EXTERNAL_LINKS_IN_APP) {{
            String startHost = Uri.parse(START_HOST_URL).getHost();
            String targetHost = uri.getHost();
            if (targetHost != null && startHost != null && !targetHost.equalsIgnoreCase(startHost)) {{
                try {{ startActivity(new Intent(Intent.ACTION_VIEW, uri)); }} catch (Exception ignored) {{ }}
                return true;
            }}
        }}
        return false;
    }}

    private void handleWebPermission(PermissionRequest request) {{
        List<String> allowed = new ArrayList<>();
        List<String> runtimePermissions = new ArrayList<>();
        for (String resource : request.getResources()) {{
            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource) && CAMERA_ENABLED) {{
                allowed.add(resource); runtimePermissions.add(Manifest.permission.CAMERA);
            }} else if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource) && MICROPHONE_ENABLED) {{
                allowed.add(resource); runtimePermissions.add(Manifest.permission.RECORD_AUDIO);
            }}
        }}
        if (allowed.isEmpty()) {{ request.deny(); return; }}
        List<String> missing = new ArrayList<>();
        for (String permission : runtimePermissions) {{
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED && !missing.contains(permission)) missing.add(permission);
        }}
        if (missing.isEmpty()) {{ request.grant(allowed.toArray(new String[0])); return; }}
        pendingPermissionRequest = request;
        pendingWebResources = allowed.toArray(new String[0]);
        requestPermissions(missing.toArray(new String[0]), WEB_PERMISSION_REQUEST);
    }}

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {{
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == WEB_PERMISSION_REQUEST && pendingPermissionRequest != null) {{
            boolean granted = grantResults.length > 0;
            for (int result : grantResults) if (result != PackageManager.PERMISSION_GRANTED) granted = false;
            if (granted) pendingPermissionRequest.grant(pendingWebResources);
            else pendingPermissionRequest.deny();
            pendingPermissionRequest = null; pendingWebResources = null;
        }}
    }}

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {{
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST && fileChooserCallback != null) {{
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK && data != null && data.getData() != null) results = new Uri[] {{ data.getData() }};
            fileChooserCallback.onReceiveValue(results);
            fileChooserCallback = null;
        }}
    }}

    @Override
    public void onBackPressed() {{
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }}

    @Override
    protected void onDestroy() {{
        if (fileChooserCallback != null) {{ fileChooserCallback.onReceiveValue(null); fileChooserCallback = null; }}
        if (webView != null) {{ webView.stopLoading(); webView.destroy(); webView = null; }}
        super.onDestroy();
    }}
}}
'''


def generate_android_project(
    config: BuildConfig,
    output_dir: Path,
    icon_path: Path | None,
    signing_dir: Path,
    signing_secret: str,
) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "", config.app_name.lower())[:22] or "websiteapp"
    package_name = config.package_name or ("com.apkie." + slug)
    project_name = _safe_project_name(config.app_name)
    app_dir = output_dir / "app"
    java_dir = app_dir / "src" / "main" / "java" / Path(*package_name.split("."))
    res_dir = app_dir / "src" / "main" / "res"
    app_dir.mkdir(parents=True, exist_ok=True)

    _write(output_dir / "settings.gradle", f'''pluginManagement {{ repositories {{ google(); mavenCentral(); gradlePluginPortal() }} }}
dependencyResolutionManagement {{ repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories {{ google(); mavenCentral() }} }}
rootProject.name = "{project_name}"
include ':app'
''')
    _write(output_dir / "build.gradle", "plugins { id 'com.android.application' version '9.4.0' apply false }\n")
    _write(output_dir / "gradle.properties", "org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\norg.gradle.parallel=false\n")
    _write(output_dir / "gradle" / "wrapper" / "gradle-wrapper.properties", "distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\ndistributionUrl=https\\://services.gradle.org/distributions/gradle-9.8-bin.zip\nnetworkTimeout=10000\nvalidateDistributionUrl=true\nzipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n")

    store_path = signing_dir / f"{package_name}.jks"
    signing_dir.mkdir(parents=True, exist_ok=True)
    password = hmac.new(signing_secret.encode("utf-8"), package_name.encode("utf-8"), hashlib.sha256).hexdigest()
    if not store_path.exists():
        keytool = os.getenv("KEYTOOL_COMMAND", "keytool")
        command = [
            keytool, "-genkeypair", "-v", "-keystore", str(store_path),
            "-storepass", password, "-keypass", password, "-alias", "apk-kie",
            "-dname", "CN=APK KIE, OU=App Build, O=APK KIE, L=NA, S=NA, C=IN",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise RuntimeError("Could not create the Android signing key: " + (result.stderr or result.stdout)[-1200:])
    shutil.copy2(store_path, app_dir / "signing.jks")
    _write(app_dir / "signing.properties", f"storePassword={password}\nkeyPassword={password}\nkeyAlias=apk-kie\n")

    gradle_app = f'''plugins {{ id 'com.android.application' }}

 def signingProps = new Properties()
 def signingFile = rootProject.file('app/signing.properties')
 signingProps.load(new FileInputStream(signingFile))

android {{
    namespace '{package_name}'
    compileSdk 36
    defaultConfig {{
        applicationId '{package_name}'
        minSdk 23
        targetSdk 36
        versionCode {config.version_code}
        versionName '{config.version_name}'
    }}
    signingConfigs {{
        release {{
            storeFile file('signing.jks')
            storePassword signingProps['storePassword']
            keyAlias signingProps['keyAlias']
            keyPassword signingProps['keyPassword']
        }}
    }}
    buildTypes {{
        release {{ signingConfig signingConfigs.release; minifyEnabled false }}
    }}
}}
'''
    _write(app_dir / "build.gradle", gradle_app)
    _write(app_dir / "src" / "main" / "AndroidManifest.xml", _manifest(config))
    _write(java_dir / "MainActivity.java", _main_activity(config, package_name))
    _write(res_dir / "values" / "colors.xml", f'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="launcher_background">{config.splash_color}</color>
    <color name="color_primary">{config.status_bar_color}</color>
    <color name="color_navigation">{config.navigation_bar_color}</color>
</resources>
''')
    _write(res_dir / "values" / "styles.xml", '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:style/Theme.Material.Light.NoActionBar">
        <item name="android:fontFamily">sans</item>
        <item name="android:colorAccent">#3157D5</item>
        <item name="android:windowLightStatusBar">false</item>
        <item name="android:windowActionModeOverlay">true</item>
        <item name="android:windowBackground">@android:color/white</item>
    </style>
    <style name="SplashTheme" parent="android:style/Theme.Material.Light.NoActionBar">
        <item name="android:windowBackground">@drawable/splash_background</item>
        <item name="android:colorAccent">#FFFFFF</item>
        <item name="android:windowLightStatusBar">false</item>
    </style>
</resources>
''')
    _write(res_dir / "drawable" / "splash_background.xml", f'''<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:drawable="@color/launcher_background" />
</layer-list>
''')
    _write(res_dir / "mipmap-anydpi-v26" / "ic_launcher.xml", '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
</adaptive-icon>
''')
    _create_icon(icon_path, res_dir, config.app_name, config.splash_color)
    return output_dir


def run_gradle_build(project_dir: Path, build_type: str, progress: ProgressCallback) -> Path:
    gradle = os.getenv("GRADLE_COMMAND", "gradle")
    task = "assembleRelease" if build_type == "apk" else "bundleRelease"
    progress(20, "Compiling Android project", "Android Gradle build started. This can take a few minutes on the first build.")
    timeout = int(os.getenv("BUILD_TIMEOUT_SECONDS", "1200"))
    try:
        process = subprocess.run(
            [gradle, "--no-daemon", "--stacktrace", task],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "JAVA_TOOL_OPTIONS": os.getenv("JAVA_TOOL_OPTIONS", "-Xmx3g")},
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Android build exceeded the {timeout}-second time limit.") from exc
    log_text = (process.stdout or "") + "\n" + (process.stderr or "")
    if process.returncode != 0:
        raise RuntimeError("Gradle build failed. Check build logs.\n" + log_text[-7000:])
    if build_type == "apk":
        artifact = project_dir / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    else:
        artifact = project_dir / "app" / "build" / "outputs" / "bundle" / "release" / "app-release.aab"
    if not artifact.exists():
        raise RuntimeError("Gradle reported success but the expected output file was not found.\n" + log_text[-4000:])
    return artifact
