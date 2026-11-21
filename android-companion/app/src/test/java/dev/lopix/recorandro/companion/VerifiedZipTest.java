package dev.lopix.recorandro.companion;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertThrows;

public class VerifiedZipTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    @Test
    public void onlyOneCanonicalSessionCookieCanBeSent() {
        String cookie = "recorandro=" + "Ab_-123".repeat(6) + 'x';
        assertEquals(cookie, VerifiedZip.sessionCookie("other=missing; " + cookie));
        assertNull(VerifiedZip.sessionCookie(cookie + "; " + cookie));
        assertNull(VerifiedZip.sessionCookie("recorandro=bad; " + cookie));
        assertNull(VerifiedZip.sessionCookie(cookie + "\r\nInjected: text"));
        assertNull(VerifiedZip.sessionCookie("other=value"));
    }

    @Test
    public void serverFilenamesCannotBecomeArbitraryPaths() {
        for (String allowed : new String[]{"part_01.zip", "full_archive.zip", "package.zip"}) {
            assertEquals(allowed, VerifiedZip.filename("attachment; filename=\"" + allowed + "\""));
        }
        for (String rejected : new String[]{"../part_01.zip", "sub/part_01.zip", "arbitrary.zip",
                "%2e%2e.zip", "part_02.zip\r\n", "file:///part_03.zip"}) {
            assertNull(VerifiedZip.filename("attachment; filename=\"" + rejected + "\""));
        }
        assertThrows(VerifiedZip.Rejected.class,
                () -> VerifiedZip.fetch(temporary.getRoot(), "http://localhost:8765/download/" + "a".repeat(32),
                        "recorandro=" + "a".repeat(43), () -> false));
        assertThrows(VerifiedZip.Rejected.class,
                () -> VerifiedZip.fetch(temporary.getRoot(), DeckEndpoint.ORIGIN + "/download/" + "a".repeat(32),
                        "missing-cookie", () -> false));
    }

    @Test
    public void copyRequiresExactLengthAndIgnoresCancelledTransfers() throws Exception {
        byte[] source = {1, 2, 3};
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] digest = VerifiedZip.copyExactly(new ByteArrayInputStream(source), output, 3, () -> false);
        assertArrayEquals(source, output.toByteArray());
        assertArrayEquals(MessageDigest.getInstance("SHA-256").digest(source), digest);
        assertThrows(IOException.class, () -> VerifiedZip.copyExactly(new ByteArrayInputStream(source), output, 2, () -> false));
        assertThrows(IOException.class, () -> VerifiedZip.copyExactly(new ByteArrayInputStream(source), output, 4, () -> false));
        assertThrows(InterruptedIOException.class,
                () -> VerifiedZip.copyExactly(new ByteArrayInputStream(source), output, 3, () -> true));
    }

    @Test
    public void malformedAndChangedStagedZipsAreRefused() throws Exception {
        File file = temporary.newFile("part_01.zip");
        Files.write(file.toPath(), new byte[]{1, 2, 3});
        assertThrows(VerifiedZip.InvalidZip.class, () -> VerifiedZip.checkZip(file));
        try (ZipOutputStream output = new ZipOutputStream(Files.newOutputStream(file.toPath()))) {
            output.putNextEntry(new ZipEntry("manifest.json"));
            output.write(new byte[]{123, 125});
            output.closeEntry();
        }
        VerifiedZip.checkZip(file);
        byte[] source = Files.readAllBytes(file.toPath());
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(source);
        VerifiedZip.Staged staged = new VerifiedZip.Staged(file, source.length, digest);
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        staged.copyTo(sink, () -> false);
        assertArrayEquals(source, sink.toByteArray());
        source[0] ^= 1;
        Files.write(file.toPath(), source);
        assertThrows(IOException.class, () -> staged.copyTo(sink, () -> false));
    }
}
