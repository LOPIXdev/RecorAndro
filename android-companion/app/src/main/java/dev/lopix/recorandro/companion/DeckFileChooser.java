package dev.lopix.recorandro.companion;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Process;
import android.provider.DocumentsContract;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient.FileChooserParams;
import android.widget.Toast;

import java.util.HashSet;
import java.util.Set;

final class DeckFileChooser {
    private static final int MAX_PHOTOS = 8; // Same count as the Deck and adapter.
    private final Activity activity;
    private ValueCallback<Uri[]> pending;
    private int requestCode = 1000;
    private int limit;

    DeckFileChooser(Activity activity) {
        this.activity = activity;
    }

    boolean isOpen() {
        return pending != null;
    }

    boolean open(ValueCallback<Uri[]> callback, FileChooserParams params) {
        int mode = params.getMode();
        boolean multiple = mode == FileChooserParams.MODE_OPEN_MULTIPLE;
        if (isOpen() || params.isCaptureEnabled() || (!multiple && mode != FileChooserParams.MODE_OPEN)) {
            callback.onReceiveValue(null);
            return true;
        }
        pending = callback;
        limit = multiple ? MAX_PHOTOS : 1;
        requestCode = requestCode == 65_535 ? 1000 : requestCode + 1;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("*/*")
                .putExtra(Intent.EXTRA_LOCAL_ONLY, true)
                .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple)
                .putExtra(Intent.EXTRA_MIME_TYPES, multiple
                        ? new String[]{"image/*", "application/octet-stream"}
                        : new String[]{"audio/*", "video/mp4", "application/octet-stream"})
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            activity.startActivityForResult(intent, requestCode);
        } catch (ActivityNotFoundException | SecurityException exception) {
            cancel();
            Toast.makeText(activity, R.string.picker_unavailable, Toast.LENGTH_LONG).show();
        }
        return true;
    }

    void onResult(int request, int result, Intent data) {
        if (!isOpen() || requestCode != request) {
            return;
        }
        if (result != Activity.RESULT_OK) {
            cancel();
            return;
        }
        Uri[] selection = null;
        try {
            selection = validatedSelection(data);
        } catch (RuntimeException exception) {
            // Malformed provider results are handled in the same way as a denied grant.
        }
        if (selection == null) {
            Toast.makeText(activity, R.string.picker_rejected, Toast.LENGTH_LONG).show();
        }
        complete(selection);
    }

    private Uri[] validatedSelection(Intent data) {
        if (data == null) {
            return null;
        }
        ClipData clip = data.getClipData();
        int count = clip == null ? 1 : clip.getItemCount();
        if (count == 0 || count > limit) {
            return null;
        }
        Uri[] selection = new Uri[count];
        Set<Uri> seen = new HashSet<>();
        for (int index = 0; index < count; index++) {
            Uri uri = clip == null ? data.getData() : clip.getItemAt(index).getUri();
            if (uri == null || !"content".equals(uri.getScheme()) || uri.getAuthority() == null
                    || uri.getUserInfo() != null || !DocumentsContract.isDocumentUri(activity, uri)
                    || activity.checkUriPermission(uri, Process.myPid(), Process.myUid(),
                            Intent.FLAG_GRANT_READ_URI_PERMISSION) != PackageManager.PERMISSION_GRANTED
                    || !seen.add(uri)) {
                return null;
            }
            selection[index] = uri;
        }
        // Chromium reads these transient grants for the HTML file inputs. The Deck and adapter
        // enforce file sizes, the combined byte limit, supported suffixes and media admission.
        return selection;
    }

    void cancel() {
        complete(null);
    }

    private void complete(Uri[] selection) {
        ValueCallback<Uri[]> callback = pending;
        pending = null;
        if (callback != null) {
            callback.onReceiveValue(selection);
        }
    }
}
