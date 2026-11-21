package dev.lopix.recorandro.companion;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Proxy;
import java.net.URL;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipException;
import java.util.zip.ZipFile;

final class VerifiedZip {
    static final String MIME = "application/zip";
    static final String CACHE_DIR = "zip-exports";
    private static final long RETENTION = TimeUnit.HOURS.toMillis(24);
    private static final Pattern COOKIE = Pattern.compile("recorandro=[a-zA-Z0-9_-]{43}");
    private static final Pattern DISPOSITION = Pattern.compile(
            "attachment; filename=\"((?:part_[0-9]+|full_archive|package)\\.zip)\"");

    private VerifiedZip() {}

    static String sessionCookie(String cookies) {
        if (cookies == null) {
            return null;
        }
        String session = null;
        for (String item : cookies.split(";")) {
            String cookie = item.trim();
            if (cookie.startsWith("recorandro=")) {
                if (session != null || !COOKIE.matcher(cookie).matches()) {
                    return null;
                }
                session = cookie;
            }
        }
        return session;
    }

    static String filename(String disposition) {
        Matcher match = DISPOSITION.matcher(disposition == null ? "" : disposition);
        return match.matches() ? match.group(1) : null;
    }

    static Staged fetch(File cache, String address, String cookie, BooleanSupplier cancelled)
            throws IOException {
        if (!DeckEndpoint.isExport(address) || cookie == null || !COOKIE.matcher(cookie).matches()) {
            throw new Rejected();
        }
        HttpURLConnection response = (HttpURLConnection) new URL(address).openConnection(Proxy.NO_PROXY);
        response.setInstanceFollowRedirects(false);
        response.setConnectTimeout(3500);
        response.setReadTimeout(30_000);
        response.setUseCaches(false);
        response.setRequestProperty("Cookie", cookie);
        response.setRequestProperty("Accept-Encoding", "identity");
        response.setRequestProperty("Connection", "close");
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(180);
        BooleanSupplier aborted = () -> cancelled.getAsBoolean() || System.nanoTime() >= deadline;
        try {
            if (aborted.getAsBoolean()) {
                throw new InterruptedIOException();
            }
            if (response.getResponseCode() != 200) {
                throw new Rejected();
            }
            long size = response.getContentLengthLong();
            String name = filename(response.getHeaderField("Content-Disposition"));
            if (!MIME.equals(response.getContentType()) || name == null || size <= 0
                    || response.getHeaderField("Transfer-Encoding") != null
                    || response.getContentEncoding() != null) {
                throw new Rejected();
            }
            File root = new File(cache, CACHE_DIR);
            Files.createDirectories(root.toPath());
            purgeExpired(root);
            if (size > root.getUsableSpace()) {
                throw new NoSpace();
            }
            File dir = Files.createTempDirectory(root.toPath(), "export-").toFile();
            File file = new File(dir, name);
            try {
                byte[] digest;
                try (InputStream input = response.getInputStream();
                     OutputStream output = Files.newOutputStream(file.toPath())) {
                    digest = copyExactly(input, output, size, aborted);
                }
                checkZip(file);
                return new Staged(file, size, digest);
            } catch (IOException | RuntimeException exception) {
                deleteFile(file);
                throw exception;
            }
        } finally {
            response.disconnect();
        }
    }

    static void checkZip(File file) throws IOException {
        // Structural transport check only. The existing Termux registry owns ZIP verification.
        try (ZipFile zip = new ZipFile(file)) {
            if (zip.size() == 0) {
                throw new InvalidZip();
            }
        } catch (ZipException exception) {
            throw new InvalidZip();
        }
    }

    static byte[] copyExactly(InputStream input, OutputStream output, long size, BooleanSupplier cancelled)
            throws IOException {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException exception) {
            throw new AssertionError(exception);
        }
        byte[] buffer = new byte[64 * 1024];
        long remaining = size;
        while (!cancelled.getAsBoolean() && !Thread.currentThread().isInterrupted()) {
            int count = input.read(buffer);
            if (count < 0 && remaining == 0 && !cancelled.getAsBoolean()) {
                return digest.digest();
            }
            if (count < 0 || count > remaining) {
                throw new IOException("ZIP length does not match");
            }
            output.write(buffer, 0, count);
            digest.update(buffer, 0, count);
            remaining -= count;
        }
        throw new InterruptedIOException();
    }

    private static void purgeExpired(File root) {
        File[] previous = root.listFiles(file -> file.getName().startsWith("export-"));
        if (previous == null) {
            return;
        }
        long cutoff = System.currentTimeMillis() - RETENTION;
        for (File directory : previous) {
            File[] entries = directory.listFiles();
            if (directory.lastModified() < cutoff && entries != null) {
                for (File entry : entries) {
                    deleteFile(entry);
                }
            }
        }
    }

    private static void deleteFile(File file) {
        try {
            Files.deleteIfExists(file.toPath());
            Files.deleteIfExists(file.getParentFile().toPath());
        } catch (IOException ignored) {
            // App-private cache is also eligible for system cleanup.
        }
    }

    static final class Staged {
        final File file;
        private final long size;
        private final byte[] digest;

        Staged(File file, long size, byte[] digest) {
            this.file = file;
            this.size = size;
            this.digest = digest;
        }

        void copyTo(OutputStream output, BooleanSupplier cancelled) throws IOException {
            try (InputStream input = Files.newInputStream(file.toPath())) {
                if (!Arrays.equals(digest, copyExactly(input, output, size, cancelled))) {
                    throw new IOException("Staged ZIP changed");
                }
            }
        }

        void delete() {
            deleteFile(file);
        }
    }

    static final class Rejected extends IOException {}
    static final class NoSpace extends IOException {}
    static final class InvalidZip extends IOException {}
}
