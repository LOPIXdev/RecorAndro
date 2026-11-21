package dev.lopix.recorandro.companion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Process;
import android.provider.DocumentsContract;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.IOException;
import java.io.InterruptedIOException;
import java.io.OutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class ZipExport {
    private static final int SAVE_REQUEST = 901;
    private final Activity activity;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private Operation active;
    private AlertDialog dialog;

    ZipExport(Activity activity) {
        this.activity = activity;
    }

    boolean isFetching() {
        return active != null && active.staged == null;
    }

    boolean isPicking() {
        return active != null && active.picking;
    }

    void start(String address, String cookies) {
        if (active != null) {
            return;
        }
        String cookie = VerifiedZip.sessionCookie(cookies);
        if (cookie == null) {
            showMessage(R.string.zip_rejected);
            return;
        }
        Operation operation = new Operation();
        active = operation;
        operation.writing = true;
        showProgress(R.string.zip_preparing);
        worker.execute(() -> fetch(operation, address, cookie));
    }

    private void fetch(Operation operation, String address, String cookie) {
        try {
            VerifiedZip.Staged zip = VerifiedZip.fetch(activity.getCacheDir(), address, cookie,
                    () -> operation.cancelled);
            activity.runOnUiThread(() -> offer(operation, zip));
        } catch (VerifiedZip.Rejected exception) {
            activity.runOnUiThread(() -> fail(operation, R.string.zip_rejected));
        } catch (VerifiedZip.NoSpace exception) {
            activity.runOnUiThread(() -> fail(operation, R.string.zip_no_space));
        } catch (VerifiedZip.InvalidZip exception) {
            activity.runOnUiThread(() -> fail(operation, R.string.zip_invalid));
        } catch (IOException | RuntimeException exception) {
            activity.runOnUiThread(() -> fail(operation, R.string.zip_failed));
        }
    }

    private void offer(Operation operation, VerifiedZip.Staged zip) {
        if (operation != active) {
            zip.delete();
            return;
        }
        operation.staged = zip;
        operation.writing = false;
        dismiss();
        dialog = new AlertDialog.Builder(activity)
                .setTitle(zip.file.getName())
                .setItems(new CharSequence[]{activity.getText(R.string.zip_save_as),
                        activity.getText(R.string.zip_share)}, (unused, option) -> {
                            if (option == 0) {
                                pickDestination(operation);
                            } else {
                                share(operation);
                            }
                        })
                .setNegativeButton(android.R.string.cancel, (unused, which) -> cancel())
                .setOnCancelListener(unused -> cancel())
                .show();
    }

    private void pickDestination(Operation operation) {
        dismiss();
        operation.picking = true;
        Intent picker = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType(VerifiedZip.MIME)
                .putExtra(Intent.EXTRA_TITLE, operation.staged.file.getName())
                .putExtra(Intent.EXTRA_LOCAL_ONLY, true)
                .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        try {
            activity.startActivityForResult(picker, SAVE_REQUEST);
        } catch (ActivityNotFoundException | SecurityException exception) {
            fail(operation, R.string.zip_destination_failed);
        }
    }

    private void share(Operation operation) {
        String authority = activity.getPackageName() + ".zip";
        try {
            Uri uri = FileProvider.getUriForFile(activity, authority, operation.staged.file);
            Intent send = new Intent(Intent.ACTION_SEND).setType(VerifiedZip.MIME)
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setClipData(ClipData.newRawUri(operation.staged.file.getName(), uri));
            activity.startActivity(Intent.createChooser(send, activity.getText(R.string.zip_share_title)));
            active = null;
            dismiss();
        } catch (ActivityNotFoundException | SecurityException | IllegalArgumentException exception) {
            fail(operation, R.string.zip_share_failed);
        }
    }

    void onResult(int request, int result, Intent data) {
        Operation operation = active;
        if (request != SAVE_REQUEST || operation == null || !operation.picking) {
            return;
        }
        operation.picking = false;
        if (result != Activity.RESULT_OK) {
            cancel();
            return;
        }
        Uri destination;
        try {
            destination = data == null ? null : data.getData();
            if (destination == null || !"content".equals(destination.getScheme())
                    || destination.getAuthority() == null || destination.getUserInfo() != null
                    || !DocumentsContract.isDocumentUri(activity, destination)
                    || activity.checkUriPermission(destination, Process.myPid(), Process.myUid(),
                            Intent.FLAG_GRANT_WRITE_URI_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
                fail(operation, R.string.zip_destination_failed);
                return;
            }
        } catch (RuntimeException exception) {
            fail(operation, R.string.zip_destination_failed);
            return;
        }
        operation.writing = true;
        showProgress(R.string.zip_saving);
        worker.execute(() -> save(operation, destination));
    }

    private void save(Operation operation, Uri destination) {
        ContentResolver resolver = activity.getContentResolver();
        int message;
        try {
            if (operation.cancelled) {
                throw new InterruptedIOException();
            }
            try (OutputStream output = resolver.openOutputStream(destination, "wt")) {
                if (output == null) {
                    throw new IOException("Save destination unavailable");
                }
                operation.staged.copyTo(output, () -> operation.cancelled);
            }
            if (operation.cancelled) {
                throw new InterruptedIOException();
            }
            message = R.string.zip_saved;
        } catch (IOException | RuntimeException exception) {
            message = removePartial(resolver, destination) ? R.string.zip_save_failed : R.string.zip_partial;
        } finally {
            operation.staged.delete();
        }
        int result = message;
        activity.runOnUiThread(() -> {
            if (operation == active) {
                active = null;
                dismiss();
                showMessage(result);
            } else if (result == R.string.zip_partial) {
                showMessage(result);
            }
        });
    }

    private static boolean removePartial(ContentResolver resolver, Uri destination) {
        try {
            return DocumentsContract.deleteDocument(resolver, destination);
        } catch (IOException | RuntimeException exception) {
            return false;
        }
    }

    private void showProgress(int message) {
        dialog = new AlertDialog.Builder(activity).setMessage(message)
                .setNegativeButton(android.R.string.cancel, (unused, which) -> cancel())
                .setOnCancelListener(unused -> cancel()).show();
    }

    private void fail(Operation operation, int message) {
        if (operation == active) {
            operation.writing = false;
            cancel();
            showMessage(message);
        }
    }

    private void showMessage(int message) {
        Toast.makeText(activity, message, Toast.LENGTH_LONG).show();
    }

    private void dismiss() {
        if (dialog != null) {
            dialog.dismiss();
            dialog = null;
        }
    }

    void cancel() {
        if (active != null) {
            Operation operation = active;
            active = null;
            operation.cancelled = true;
            if (!operation.writing && operation.staged != null) {
                operation.staged.delete();
            }
        }
        dismiss();
    }

    void destroy() {
        cancel();
        worker.shutdown();
    }

    private static final class Operation {
        volatile boolean cancelled;
        boolean writing;
        boolean picking;
        VerifiedZip.Staged staged;
    }
}
