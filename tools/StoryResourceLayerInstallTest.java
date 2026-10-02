package io.kamihama.magianative;

import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import org.json.JSONObject;

/** Real production installer replay on supplied published ZIPs, in an empty test directory. */
public final class StoryResourceLayerInstallTest {
    private static final String PREFIX = "madomagi/resource/scenario/json/adv/";
    private static final String[] REGRESSIONS = {
        PREFIX + "scenario_1/101704-1_YTq8g.json",
        PREFIX + "scenario_1/101802-21_a7FVS.json",
        PREFIX + "scenario_5/506905-5_ifs6e.json",
        PREFIX + "scenario_5/506909-9_Arnzs.json"
    };
    private static void require(boolean value, String description) {
        if (!value) throw new AssertionError(description);
    }
    private static byte[] bytes(ZipFile zip, String name) throws Exception {
        java.io.InputStream stream = zip.getInputStream(zip.getEntry(name));
        try {
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[65536]; int count;
            while ((count = stream.read(buffer)) != -1) out.write(buffer, 0, count);
            return out.toByteArray();
        } finally { stream.close(); }
    }
    private static int verify(File archive, File root) throws Exception {
        int count = 0;
        ZipFile zip = new ZipFile(archive);
        try {
            for (Enumeration<? extends ZipEntry> all = zip.entries(); all.hasMoreElements();) {
                ZipEntry entry = all.nextElement();
                if (entry.isDirectory()) continue;
                require(Arrays.equals(bytes(zip, entry.getName()), Files.readAllBytes(new File(root, entry.getName()).toPath())),
                        "Installed bytes differ: " + entry.getName());
                ++count;
            }
        } finally { zip.close(); }
        return count;
    }
    public static void main(String[] args) throws Exception {
        require(args.length == 6, "js103 scenario3322 delta21 scenarioNew deltaNew emptyRoot");
        File js = new File(args[0]), oldScenario = new File(args[1]), oldDelta = new File(args[2]);
        File scenario = new File(args[3]), delta = new File(args[4]), root = new File(args[5]);
        require(!root.exists(), "Never test on an existing installation");
        require(root.mkdirs(), "Cannot create isolated test directory");
        System.out.println("STAGE old full Scenario");
        CNHotUpdateTx.apply(oldScenario, root, "scenario");
        System.out.println("STAGE frozen JS");
        CNHotUpdateTx.apply(js, root, "js");
        System.out.println("STAGE old delta last");
        CNJsDelta.apply(oldDelta, root, 103, 21);
        int regressions = 0;
        ZipFile before = new ZipFile(oldScenario), legacy = new ZipFile(oldDelta);
        try {
            for (String name : REGRESSIONS) {
                byte[] actual = Files.readAllBytes(new File(root, name).toPath());
                require(Arrays.equals(actual, bytes(legacy, name)), "Old delta did not reproduce");
                require(!Arrays.equals(actual, bytes(before, name)), "Expected newer scenario was not overwritten");
                ++regressions;
            }
        } finally { before.close(); legacy.close(); }
        require(CNJsDelta.installedMatches(root, 103, 21), "Counterexample must still pass old latest check");
        System.out.println("OLD_PRODUCTION_REPLAY_CONFIRMED regressions=" + regressions);
        System.out.println("STAGE current full Scenario transaction");
        CNHotUpdateTx.apply(scenario, root, "scenario");
        CNJsDelta.reapplyCached(root, 103);
        ZipFile newer = new ZipFile(scenario);
        try {
            for (String name : REGRESSIONS)
                require(!Arrays.equals(Files.readAllBytes(new File(root, name).toPath()), bytes(newer, name)),
                        "Expected cached old-delta replay counterexample");
        } finally { newer.close(); }
        ZipFile dz = new ZipFile(delta); int version;
        try { version = new JSONObject(new String(bytes(dz, "magica/.cn_js_delta.json"), "UTF-8")).getInt("version"); }
        finally { dz.close(); }
        CNJsDelta.apply(delta, root, 103, version);
        int scenarioCount = verify(scenario, root), deltaCount = verify(delta, root);
        require(CNJsDelta.installedMatches(root, 103, version), "New final state does not match supplement");
        System.out.println("STAGE current full Scenario transaction");
        CNHotUpdateTx.apply(scenario, root, "scenario");
        CNJsDelta.reapplyCached(root, 103);
        require(verify(scenario, root) == scenarioCount, "Scenario reinstall regression");
        require(verify(delta, root) == deltaCount, "Cached new supplement replay regression");
        JSONObject report = new JSONObject();
        report.put("productionInstallerClasses", true).put("oldRegressionCount", regressions)
              .put("oldLatestCheckFalsePositiveReproduced", true).put("scenarioFilesVerified", scenarioCount)
              .put("deltaFilesVerified", deltaCount).put("deltaVersion", version)
              .put("scenarioReinstallThenCachedDeltaPassed", true);
        Files.write(new File(root.getParentFile(), "production-installer-replay.json").toPath(), report.toString(2).getBytes("UTF-8"));
        System.out.println("PRODUCTION_RESOURCE_LAYER_REPLAY_PASS " + report.toString());
    }
}
