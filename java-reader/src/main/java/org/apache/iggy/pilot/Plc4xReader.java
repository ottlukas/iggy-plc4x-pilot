package org.apache.iggy.pilot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.plc4x.java.DefaultPlcDriverManager;
import org.apache.plc4x.java.api.PlcConnection;
import org.apache.plc4x.java.api.messages.PlcReadResponse;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

public final class Plc4xReader {
    private static final ObjectMapper JSON = new ObjectMapper();

    record Tag(String name, String address) {}

    public static void main(String[] args) throws Exception {
        Map<String, String> options = new LinkedHashMap<>();
        List<Tag> tags = new ArrayList<>();
        for (int index = 0; index < args.length; index++) {
            String key = args[index];
            if (key.equals("--tag")) {
                String[] parts = args[++index].split("=", 2);
                if (parts.length != 2) throw new IllegalArgumentException("tag must be NAME=ADDRESS");
                tags.add(new Tag(parts[0], parts[1]));
            } else if (key.startsWith("--") && index + 1 < args.length) {
                options.put(key, args[++index]);
            } else {
                throw new IllegalArgumentException("unexpected argument: " + key);
            }
        }

        String endpoint = required(options, "--endpoint");
        String device = required(options, "--device");
        String devicePrefix = required(options, "--device-prefix");
        long pollMs = Long.parseLong(required(options, "--poll-ms"));
        if (tags.isEmpty()) throw new IllegalArgumentException("at least one --tag is required");

        DefaultPlcDriverManager manager = new DefaultPlcDriverManager();
        while (!Thread.currentThread().isInterrupted()) {
            try (PlcConnection connection = manager.getConnection(endpoint)) {
                PlcReadResponse response = readTags(connection, tags);
                for (Tag tag : tags) {
                    Map<String, Object> reading = toReading(
                            response, tag, devicePrefix + "." + device, System.currentTimeMillis());
                    if (reading == null) {
                        System.err.println("PLC4X read failed for " + tag.name() + ": " + response.getResponseCode(tag.name()));
                        continue;
                    }
                    System.out.println("READING:" + JSON.writeValueAsString(reading));
                    System.out.flush();
                }
            } catch (Exception error) {
                System.err.println("PLC4X connection/read error: " + error.getMessage());
            }
            Thread.sleep(pollMs);
        }
    }

    private static String required(Map<String, String> options, String key) {
        String value = options.get(key);
        if (value == null || value.isBlank()) throw new IllegalArgumentException("missing " + key);
        return value;
    }

    static Map<String, Object> toReading(
            PlcReadResponse response, Tag tag, String device, long timestamp) {
        if (!response.getResponseCode(tag.name()).name().equals("OK")) return null;
        Map<String, Object> reading = new LinkedHashMap<>();
        reading.put("device", device);
        reading.put("timestamp", timestamp);
        reading.put("measurements", List.of(tag.name()));
        reading.put("values", List.of(response.getObject(tag.name())));
        return reading;
    }

    static PlcReadResponse readTags(PlcConnection connection, List<Tag> tags) throws Exception {
        var request = connection.readRequestBuilder();
        for (Tag tag : tags) request.addTagAddress(tag.name(), tag.address());
        return request.build().execute().get(10, TimeUnit.SECONDS);
    }
}