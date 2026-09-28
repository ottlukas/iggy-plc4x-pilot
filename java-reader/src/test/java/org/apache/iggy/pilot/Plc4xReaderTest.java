package org.apache.iggy.pilot;

import org.apache.plc4x.java.api.messages.PlcReadResponse;
import org.apache.plc4x.java.api.messages.PlcReadRequest;
import org.apache.plc4x.java.api.types.PlcResponseCode;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.List;
import java.util.concurrent.CompletableFuture;

import org.apache.plc4x.java.api.PlcConnection;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class Plc4xReaderTest {
    @Test
    void mapsSuccessfulModbusResponseToTreeReading() {
        PlcReadResponse response = mock(PlcReadResponse.class);
        when(response.getResponseCode("temperature")).thenReturn(PlcResponseCode.OK);
        when(response.getObject("temperature")).thenReturn(237);

        Map<String, Object> reading = Plc4xReader.toReading(
                response,
                new Plc4xReader.Tag("temperature", "holding-register:0:UINT"),
                "root.sg.line_1",
                1234L);

        assertEquals("root.sg.line_1", reading.get("device"));
        assertEquals(1234L, reading.get("timestamp"));
        assertEquals(java.util.List.of("temperature"), reading.get("measurements"));
        assertEquals(java.util.List.of(237), reading.get("values"));
        verify(response).getObject("temperature");
    }

    @Test
    void readsConfiguredTagThroughMockedPlcConnection() throws Exception {
        PlcConnection connection = mock(PlcConnection.class);
        PlcReadRequest.Builder requestBuilder = mock(PlcReadRequest.Builder.class);
        PlcReadRequest request = mock(PlcReadRequest.class);
        PlcReadResponse response = mock(PlcReadResponse.class);
        Plc4xReader.Tag tag = new Plc4xReader.Tag("temperature", "holding-register:0:UINT");
        when(connection.readRequestBuilder()).thenReturn(requestBuilder);
        when(requestBuilder.addTagAddress(tag.name(), tag.address())).thenReturn(requestBuilder);
        when(requestBuilder.build()).thenReturn(request);
        when(request.execute()).thenAnswer(ignored -> CompletableFuture.completedFuture(response));
        when(response.getResponseCode("temperature")).thenReturn(PlcResponseCode.OK);
        when(response.getObject("temperature")).thenReturn(237);

        PlcReadResponse actual = Plc4xReader.readTags(connection, List.of(tag));
        Map<String, Object> reading = Plc4xReader.toReading(actual, tag, "root.sg.line_1", 1234L);

        assertEquals(java.util.List.of(237), reading.get("values"));
        verify(connection.readRequestBuilder()).addTagAddress("temperature", "holding-register:0:UINT");
    }

    @Test
    void skipsFailedTagResponse() {
        PlcReadResponse response = mock(PlcReadResponse.class);
        when(response.getResponseCode("temperature")).thenReturn(PlcResponseCode.ACCESS_DENIED);

        assertNull(Plc4xReader.toReading(
                response,
                new Plc4xReader.Tag("temperature", "holding-register:0:UINT"),
                "root.sg.line_1",
                1234L));
    }
}
