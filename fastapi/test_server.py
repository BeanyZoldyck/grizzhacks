"""FastAPI: ESP32 /ping, voice lesson ingest for same-LAN mobile apps."""

from __future__ import annotations

import io
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
import uvicorn

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "client"))

load_dotenv(_ROOT / "mongo" / ".env")
load_dotenv(_ROOT / ".env", override=False)

from ai_lesson import (  # noqa: E402
    generate_lesson,
    save_tool_xml_files,
    save_visualization_xml_files,
)

app = FastAPI(title="Embettered host", version="1.0.0")
_TOOL_XML_DIR = _ROOT / "fastapi" / "generated_tool_xml"
_VISUAL_XML_DIR = _ROOT / "fastapi" / "generated_visualization_xml"
_HARDCODED_LESSON_XML_RESPONSE = {
    "ok": True,
    "lesson_name": "Introduction_to_LEDs",
    "step_count": 3,
    "tts_text": (
        "Identify the two leads of the LED. The longer lead is the ANODE (positive) and "
        "the shorter lead is the CATHODE (negative). The cathode also has a flat edge on "
        "the LED housing. Current flows from Anode to Cathode. Always connect a resistor "
        "(typically 220Ω to 1kΩ) in series with an LED to limit current and prevent damage. "
        "Connect the resistor to the Anode, then to your microcontroller pin. Connect the "
        "Cathode to GND. The microcontroller pin outputs current to light the LED. To turn "
        "ON the LED, set the microcontroller pin HIGH (logic 1). To turn it OFF, set the "
        "pin LOW (logic 0). Use pinMode() to configure the pin as OUTPUT, then digitalWrite() "
        "to control it. Example: pinMode(LED_PIN, OUTPUT); digitalWrite(LED_PIN, HIGH);"
    ),
    "ws_response": None,
    "tool_xml_count": 3,
    "tool_xml_files": [
        "/home/sigma/projects/repos/grizzhacks/fastapi/generated_tool_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_step_01_tool.xml",
        "/home/sigma/projects/repos/grizzhacks/fastapi/generated_tool_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_step_02_tool.xml",
        "/home/sigma/projects/repos/grizzhacks/fastapi/generated_tool_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_step_03_tool.xml",
    ],
    "tool_xml_documents": [
        {
            "step": 1,
            "path": "/home/sigma/projects/repos/grizzhacks/fastapi/generated_tool_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_step_01_tool.xml",
            "xml": """<?xml version='1.0' encoding='utf-8'?>
<VisionProgramInformation xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Erode />
  <Dilate />
  <FlipImage>
    <ID>0</ID>
  </FlipImage>
  <BaseLine />
  <Configuration>
    <SchemaVersion>1.3</SchemaVersion>
    <SaveDate>2026-03-29-06-42-17</SaveDate>
  </Configuration>
  <Tool>
    <ToolName>Tool01</ToolName>
    <ToolType>Brightness</ToolType>
    <UseOriginalImage>false</UseOriginalImage>
    <Filters xsi:type="RGB">
      <ColorMin xsi:type="xsd:string">Black</ColorMin>
      <ColorMax xsi:type="xsd:string">Red</ColorMax>
    </Filters>
    <Region>
      <Vertex>
        <X>146</X>
        <Y>133</Y>
      </Vertex>
      <Vertex>
        <X>354</X>
        <Y>133</Y>
      </Vertex>
      <Vertex>
        <X>354</X>
        <Y>265</Y>
      </Vertex>
      <Vertex>
        <X>146</X>
        <Y>265</Y>
      </Vertex>
      <OriginOffset>
        <X>0</X>
        <Y>0</Y>
      </OriginOffset>
    </Region>
    <XLink />
    <YLink />
    <AngleLink />
    <ExcludeFromTrueList>false</ExcludeFromTrueList>
    <ImageBasedOrigin>true</ImageBasedOrigin>
    <CenterResult>true</CenterResult>
    <ThoroughSearch>false</ThoroughSearch>
    <Inputs>
      <Key>ThresholdMin</Key>
      <Value xsi:type="xsd:int">29</Value>
    </Inputs>
    <Inputs>
      <Key>ThresholdMax</Key>
      <Value xsi:type="xsd:int">255</Value>
    </Inputs>
    <Outputs>
      <Key>InRange</Key>
      <Enabled>true</Enabled>
    </Outputs>
    <Outputs>
      <Key>Count</Key>
      <Enabled>false</Enabled>
    </Outputs>
    <Outputs>
      <Key>Avg</Key>
      <Enabled>false</Enabled>
    </Outputs>
  </Tool>
  <Camera>
    <CameraType>WEBCAM</CameraType>
    <VideoMode>
      <Sensor>COLOR</Sensor>
      <Width>1104</Width>
      <Height>828</Height>
      <FrameRate>10</FrameRate>
      <PixelFormat>-1</PixelFormat>
      <SensorMode>-1</SensorMode>
      <X>0</X>
      <Y>0</Y>
    </VideoMode>
    <DevicePath />
    <BackupIdentifier />
    <Name>Generated Camera Step 1</Name>
    <Alias>Camera1</Alias>
    <RangeMin>-1</RangeMin>
    <RangeMax>-1</RangeMax>
  </Camera>
</VisionProgramInformation>""",
        },
        {
            "step": 2,
            "path": "/home/sigma/projects/repos/grizzhacks/fastapi/generated_tool_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_step_02_tool.xml",
            "xml": """<?xml version='1.0' encoding='utf-8'?>
<VisionProgramInformation xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Erode />
  <Dilate />
  <FlipImage>
    <ID>0</ID>
  </FlipImage>
  <BaseLine />
  <Configuration>
    <SchemaVersion>1.3</SchemaVersion>
    <SaveDate>2026-03-29-06-42-17</SaveDate>
  </Configuration>
  <Tool>
    <ToolName>Tool01</ToolName>
    <ToolType>Brightness</ToolType>
    <UseOriginalImage>false</UseOriginalImage>
    <Filters xsi:type="RGB">
      <ColorMin xsi:type="xsd:string">Black</ColorMin>
      <ColorMax xsi:type="xsd:string">Red</ColorMax>
    </Filters>
    <Region>
      <Vertex>
        <X>120</X>
        <Y>107</Y>
      </Vertex>
      <Vertex>
        <X>380</X>
        <Y>107</Y>
      </Vertex>
      <Vertex>
        <X>380</X>
        <Y>265</Y>
      </Vertex>
      <Vertex>
        <X>120</X>
        <Y>265</Y>
      </Vertex>
      <OriginOffset>
        <X>0</X>
        <Y>0</Y>
      </OriginOffset>
    </Region>
    <XLink />
    <YLink />
    <AngleLink />
    <ExcludeFromTrueList>false</ExcludeFromTrueList>
    <ImageBasedOrigin>true</ImageBasedOrigin>
    <CenterResult>true</CenterResult>
    <ThoroughSearch>false</ThoroughSearch>
    <Inputs>
      <Key>ThresholdMin</Key>
      <Value xsi:type="xsd:int">29</Value>
    </Inputs>
    <Inputs>
      <Key>ThresholdMax</Key>
      <Value xsi:type="xsd:int">255</Value>
    </Inputs>
    <Outputs>
      <Key>InRange</Key>
      <Enabled>true</Enabled>
    </Outputs>
    <Outputs>
      <Key>Count</Key>
      <Enabled>false</Enabled>
    </Outputs>
    <Outputs>
      <Key>Avg</Key>
      <Enabled>false</Enabled>
    </Outputs>
  </Tool>
  <Camera>
    <CameraType>WEBCAM</CameraType>
    <VideoMode>
      <Sensor>COLOR</Sensor>
      <Width>1104</Width>
      <Height>828</Height>
      <FrameRate>10</FrameRate>
      <PixelFormat>-1</PixelFormat>
      <SensorMode>-1</SensorMode>
      <X>0</X>
      <Y>0</Y>
    </VideoMode>
    <DevicePath />
    <BackupIdentifier />
    <Name>Generated Camera Step 2</Name>
    <Alias>Camera1</Alias>
    <RangeMin>-1</RangeMin>
    <RangeMax>-1</RangeMax>
  </Camera>
</VisionProgramInformation>""",
        },
        {
            "step": 3,
            "path": "/home/sigma/projects/repos/grizzhacks/fastapi/generated_tool_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_step_03_tool.xml",
            "xml": """<?xml version='1.0' encoding='utf-8'?>
<VisionProgramInformation xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Erode />
  <Dilate />
  <FlipImage>
    <ID>0</ID>
  </FlipImage>
  <BaseLine />
  <Configuration>
    <SchemaVersion>1.3</SchemaVersion>
    <SaveDate>2026-03-29-06-42-17</SaveDate>
  </Configuration>
  <Tool>
    <ToolName>Tool01</ToolName>
    <ToolType>Brightness</ToolType>
    <UseOriginalImage>false</UseOriginalImage>
    <Filters xsi:type="RGB">
      <ColorMin xsi:type="xsd:string">Black</ColorMin>
      <ColorMax xsi:type="xsd:string">Red</ColorMax>
    </Filters>
    <Region>
      <Vertex>
        <X>153</X>
        <Y>81</Y>
      </Vertex>
      <Vertex>
        <X>360</X>
        <Y>81</Y>
      </Vertex>
      <Vertex>
        <X>360</X>
        <Y>265</Y>
      </Vertex>
      <Vertex>
        <X>153</X>
        <Y>265</Y>
      </Vertex>
      <OriginOffset>
        <X>0</X>
        <Y>0</Y>
      </OriginOffset>
    </Region>
    <XLink />
    <YLink />
    <AngleLink />
    <ExcludeFromTrueList>false</ExcludeFromTrueList>
    <ImageBasedOrigin>true</ImageBasedOrigin>
    <CenterResult>true</CenterResult>
    <ThoroughSearch>false</ThoroughSearch>
    <Inputs>
      <Key>ThresholdMin</Key>
      <Value xsi:type="xsd:int">29</Value>
    </Inputs>
    <Inputs>
      <Key>ThresholdMax</Key>
      <Value xsi:type="xsd:int">255</Value>
    </Inputs>
    <Outputs>
      <Key>InRange</Key>
      <Enabled>true</Enabled>
    </Outputs>
    <Outputs>
      <Key>Count</Key>
      <Enabled>false</Enabled>
    </Outputs>
    <Outputs>
      <Key>Avg</Key>
      <Enabled>false</Enabled>
    </Outputs>
  </Tool>
  <Camera>
    <CameraType>WEBCAM</CameraType>
    <VideoMode>
      <Sensor>COLOR</Sensor>
      <Width>1104</Width>
      <Height>828</Height>
      <FrameRate>10</FrameRate>
      <PixelFormat>-1</PixelFormat>
      <SensorMode>-1</SensorMode>
      <X>0</X>
      <Y>0</Y>
    </VideoMode>
    <DevicePath />
    <BackupIdentifier />
    <Name>Generated Camera Step 3</Name>
    <Alias>Camera1</Alias>
    <RangeMin>-1</RangeMin>
    <RangeMax>-1</RangeMax>
  </Camera>
</VisionProgramInformation>""",
        },
    ],
    "visualization_xml_count": 1,
    "visualization_xml_files": [
        "/home/sigma/projects/repos/grizzhacks/fastapi/generated_visualization_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_visualization.xml",
    ],
    "visualization_xml_documents": [
        {
            "path": "/home/sigma/projects/repos/grizzhacks/fastapi/generated_visualization_xml/Introduction_to_LEDs_20260329_064217/Introduction_to_LEDs_visualization.xml",
            "xml": """<?xml version='1.0' encoding='utf-8'?>
<CommandInformation xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://tempuri.org/CommandInformation.xsd">
  <Metadata>
    <SoftwareVersion>25.3.4.0</SoftwareVersion>
    <LicenseSerial>000000</LicenseSerial>
    <SaveDate>2026-03-29T06:42:17</SaveDate>
  </Metadata>
  <Command>
    <Line>1</Line>
    <Type>StartProgram</Type>
    <Description>Introduction_to_LEDs workflow</Description>
  </Command>
  <Command>
    <Line>2</Line>
    <Type>StepStart</Type>
    <Description>Step Start</Description>
    <Comment>Understanding LED polarity and identification</Comment>
    <Step>1</Step>
  </Command>
  <Command>
    <Line>3</Line>
    <Type>ClearCanvas</Type>
    <Description>Clear Canvas [All]</Description>
    <Canvas>1024</Canvas>
  </Command>
  <Command>
    <Line>4</Line>
    <Type>VDFGraphics</Type>
    <Description>led_polarity.svg; Color: 0,255,0</Description>
    <FileName>led_polarity.svg</FileName>
    <Canvas>1</Canvas>
    <X>300.0</X>
    <Y>200.0</Y>
    <Width>400.0</Width>
    <Height>250.0</Height>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FilePath>C:\\Program Files\\OPS Solutions\\Light Guide Systems\\VDFGraphics\\Shapes\\led_polarity.svg</FilePath>
    <FilterColor>0,255,0</FilterColor>
  </Command>
  <Command>
    <Line>5</Line>
    <Type>VDFText</Type>
    <Description>"LED POLARITY"</Description>
    <Text>LED POLARITY</Text>
    <Canvas>1</Canvas>
    <X>362.0</X>
    <Y>50.0</Y>
    <Width>300.0</Width>
    <Height>50.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>255,255,255,255</TextColor>
    <FontSize>28</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>6</Line>
    <Type>VDFText</Type>
    <Description>"Anode (+)"</Description>
    <Text>Anode (+)</Text>
    <Canvas>1</Canvas>
    <X>500.0</X>
    <Y>280.0</Y>
    <Width>150.0</Width>
    <Height>30.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>255,0,0,255</TextColor>
    <FontSize>18</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>7</Line>
    <Type>VDFText</Type>
    <Description>"Cathode (-)"</Description>
    <Text>Cathode (-)</Text>
    <Canvas>1</Canvas>
    <X>300.0</X>
    <Y>280.0</Y>
    <Width>150.0</Width>
    <Height>30.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>0,0,255,255</TextColor>
    <FontSize>18</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>8</Line>
    <Type>Confirmation</Type>
    <Description>Wait For [Manual Confirmation]</Description>
    <Variable>Manual Confirmation</Variable>
    <ConfirmType>Forward</ConfirmType>
    <StepsToMove>1</StepsToMove>
  </Command>
  <Command>
    <Line>9</Line>
    <Type>StepStart</Type>
    <Description>Step Start</Description>
    <Comment>LED connection with current-limiting resistor</Comment>
    <Step>2</Step>
  </Command>
  <Command>
    <Line>10</Line>
    <Type>ClearCanvas</Type>
    <Description>Clear Canvas [All]</Description>
    <Canvas>1024</Canvas>
  </Command>
  <Command>
    <Line>11</Line>
    <Type>VDFGraphics</Type>
    <Description>led_circuit.svg; Color: 255,255,255</Description>
    <FileName>led_circuit.svg</FileName>
    <Canvas>1</Canvas>
    <X>250.0</X>
    <Y>150.0</Y>
    <Width>500.0</Width>
    <Height>300.0</Height>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FilePath>C:\\Program Files\\OPS Solutions\\Light Guide Systems\\VDFGraphics\\Shapes\\led_circuit.svg</FilePath>
    <FilterColor>255,255,255</FilterColor>
  </Command>
  <Command>
    <Line>12</Line>
    <Type>VDFText</Type>
    <Description>"LED CIRCUIT DIAGRAM"</Description>
    <Text>LED CIRCUIT DIAGRAM</Text>
    <Canvas>1</Canvas>
    <X>362.0</X>
    <Y>50.0</Y>
    <Width>300.0</Width>
    <Height>50.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>255,255,255,255</TextColor>
    <FontSize>28</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>13</Line>
    <Type>VDFText</Type>
    <Description>"MCU Pin"</Description>
    <Text>MCU Pin</Text>
    <Canvas>1</Canvas>
    <X>200.0</X>
    <Y>200.0</Y>
    <Width>100.0</Width>
    <Height>30.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>255,255,0,255</TextColor>
    <FontSize>16</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>14</Line>
    <Type>VDFText</Type>
    <Description>"R (220Ω-1kΩ)"</Description>
    <Text>R (220Ω-1kΩ)</Text>
    <Canvas>1</Canvas>
    <X>400.0</X>
    <Y>120.0</Y>
    <Width>120.0</Width>
    <Height>30.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>255,255,255,255</TextColor>
    <FontSize>14</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>15</Line>
    <Type>VDFText</Type>
    <Description>"GND"</Description>
    <Text>GND</Text>
    <Canvas>1</Canvas>
    <X>650.0</X>
    <Y>350.0</Y>
    <Width>80.0</Width>
    <Height>30.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>0,255,0,255</TextColor>
    <FontSize>16</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>16</Line>
    <Type>Confirmation</Type>
    <Description>Wait For [Manual Confirmation]</Description>
    <Variable>Manual Confirmation</Variable>
    <ConfirmType>Forward</ConfirmType>
    <StepsToMove>1</StepsToMove>
  </Command>
  <Command>
    <Line>17</Line>
    <Type>StepStart</Type>
    <Description>Step Start</Description>
    <Comment>Writing LED control code</Comment>
    <Step>3</Step>
  </Command>
  <Command>
    <Line>18</Line>
    <Type>ClearCanvas</Type>
    <Description>Clear Canvas [All]</Description>
    <Canvas>1024</Canvas>
  </Command>
  <Command>
    <Line>19</Line>
    <Type>VDFText</Type>
    <Description>"LED CONTROL CODE"</Description>
    <Text>LED CONTROL CODE</Text>
    <Canvas>1</Canvas>
    <X>262.0</X>
    <Y>30.0</Y>
    <Width>500.0</Width>
    <Height>50.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>255,255,255,255</TextColor>
    <FontSize>28</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>20</Line>
    <Type>VDFGraphics</Type>
    <Description>code_block.svg; Color: 30,30,30</Description>
    <FileName>code_block.svg</FileName>
    <Canvas>1</Canvas>
    <X>312.0</X>
    <Y>100.0</Y>
    <Width>400.0</Width>
    <Height>350.0</Height>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FilePath>C:\\Program Files\\OPS Solutions\\Light Guide Systems\\VDFGraphics\\Shapes\\code_block.svg</FilePath>
    <FilterColor>30,30,30</FilterColor>
  </Command>
  <Command>
    <Line>21</Line>
    <Type>VDFText</Type>
    <Description>"const int LED_PIN = 13;

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH); // LED ON
  delay(1000);
  digitalWrite(LED_PIN, LOW);  // LED OFF
  delay(1000);
}"</Description>
    <Text>const int LED_PIN = 13;

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH); // LED ON
  delay(1000);
  digitalWrite(LED_PIN, LOW);  // LED OFF
  delay(1000);
}</Text>
    <Canvas>1</Canvas>
    <X>332.0</X>
    <Y>120.0</Y>
    <Width>360.0</Width>
    <Height>300.0</Height>
    <BlinkType>None</BlinkType>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FontName>Microsoft Sans Serif</FontName>
    <TextColor>0,255,0,255</TextColor>
    <FontSize>16</FontSize>
    <Justify>0</Justify>
  </Command>
  <Command>
    <Line>22</Line>
    <Type>VDFGraphics</Type>
    <Description>Line.svg; Color: 0,255,0</Description>
    <FileName>Line.svg</FileName>
    <Canvas>1</Canvas>
    <X>312.0</X>
    <Y>100.0</Y>
    <Width>400.0</Width>
    <Height>350.0</Height>
    <BlinkRate>1000</BlinkRate>
    <Movements>None</Movements>
    <FilePath>C:\\Program Files\\OPS Solutions\\Light Guide Systems\\VDFGraphics\\Shapes\\Line.svg</FilePath>
    <FilterColor>0,255,0</FilterColor>
  </Command>
  <Command>
    <Line>23</Line>
    <Type>Confirmation</Type>
    <Description>Wait For [Manual Confirmation]</Description>
    <Variable>Manual Confirmation</Variable>
    <ConfirmType>Forward</ConfirmType>
    <StepsToMove>1</StepsToMove>
  </Command>
  <Command>
    <Line>24</Line>
    <Type>EndProgram</Type>
    <Description>End of Workflow</Description>
    <FileName>Introduction_to_LEDs.xml</FileName>
    <FilePath>C:\\Program Files\\OPS Solutions\\Light Guide Systems\\VDFPrograms\\Introduction_to_LEDs.xml</FilePath>
  </Command>
</CommandInformation>""",
        }
    ],
    "transcript": "Create a 3-step LED lesson",
}


class Ping(BaseModel):
    msg: str
    device: str
    id: str


class LessonTextBody(BaseModel):
    query: str = Field(..., min_length=1)
    provider: str = Field(default="openai", pattern="^(openai|anthropic)$")


def _tts_text_from_lesson(lesson_data: dict) -> str:
    steps = lesson_data.get("steps") or []
    if not steps:
        return (lesson_data.get("description") or "").strip()
    parts: list[str] = []
    for step in steps[:5]:
        text = (step.get("instruction") or step.get("description") or "").strip()
        if text:
            parts.append(text)
    return " ".join(parts) if parts else (lesson_data.get("lesson_name") or "").strip()


def _transcribe_whisper(data: bytes, filename: str | None) -> str:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="openai package not installed on server",
        ) from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set (required for Whisper)",
        )

    client = OpenAI(api_key=api_key)
    buf = io.BytesIO(data)
    buf.name = filename or "audio.m4a"
    try:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Whisper transcription failed: {e!s}",
        ) from e
    return transcription.text.strip()


def _speak_query_with_elevenlabs(query: str) -> bytes:
    """Convert input query text to spoken audio with ElevenLabs."""
    text = query.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty query")

    try:
        from elevenlabs.client import ElevenLabs
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="elevenlabs package not installed on server",
        ) from e

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ELEVENLABS_API_KEY is not set",
        )

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    client = ElevenLabs(api_key=api_key)

    try:
        audio_stream = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id=model_id,
            text=text,
            output_format="mp3_44100_128",
        )
        audio = b"".join(audio_stream)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"ElevenLabs TTS failed: {e!s}",
        ) from e

    if not audio:
        raise HTTPException(status_code=502, detail="ElevenLabs returned empty audio")
    return audio


async def _run_lesson_from_query(
    query: str,
    *,
    provider: str = "openai",
    persist_mongo: bool = True,
    include_tool_xml: bool = False,
    include_visualization_xml: bool = False,
) -> dict:
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty transcript or query")

    try:
        lesson_data = generate_lesson(query, provider=provider)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    lesson_name = lesson_data.get("lesson_name", "Generated_Lesson")
    steps = lesson_data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise HTTPException(
            status_code=502,
            detail="Lesson JSON missing 'steps' array",
        )

    tts_text = _tts_text_from_lesson(lesson_data)
    persist_response: dict | None = None
    tool_xml_documents: list[dict] = []
    visualization_xml_documents: list[dict] = []

    if include_tool_xml:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = _TOOL_XML_DIR / f"{lesson_name}_{timestamp}"
            artifacts = save_tool_xml_files(lesson_name, steps, str(out_dir))
            tool_xml_documents = [
                {
                    "step": a["step"],
                    "path": str(a["path"]),
                    "xml": a["xml"],
                }
                for a in artifacts
            ]
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Tool XML generation failed: {e!s}",
            ) from e

    if include_visualization_xml:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = _VISUAL_XML_DIR / f"{lesson_name}_{timestamp}"
            artifacts = save_visualization_xml_files(lesson_name, steps, str(out_dir))
            visualization_xml_documents = [
                {
                    "path": str(a["path"]),
                    "xml": a["xml"],
                }
                for a in artifacts
            ]
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Visualization XML generation failed: {e!s}",
            ) from e

    # Mongo persistence intentionally disabled for now.
    # if persist_mongo:
    #     try:
    #         persist_response = await send_lesson(
    #             lesson_name,
    #             steps,
    #             verbose=False,
    #             description=raw_desc if isinstance(raw_desc, str) else None,
    #             source="fastapi",
    #             metadata={"tool_xml_documents": tool_xml_documents}
    #             if tool_xml_documents
    #             else None,
    #         )
    #     except Exception as e:
    #         raise HTTPException(
    #             status_code=502,
    #             detail=f"MongoDB persist failed: {e!s}",
    #         ) from e

    return {
        "ok": True,
        "lesson_name": lesson_name,
        "step_count": len(steps),
        "tts_text": tts_text,
        "ws_response": persist_response,
        "tool_xml_count": len(tool_xml_documents),
        "tool_xml_files": [doc["path"] for doc in tool_xml_documents],
        "tool_xml_documents": tool_xml_documents,
        "visualization_xml_count": len(visualization_xml_documents),
        "visualization_xml_files": [doc["path"] for doc in visualization_xml_documents],
        "visualization_xml_documents": visualization_xml_documents,
    }


@app.post("/update")
async def receive_ping(p: Ping):
    print(f"Received ping from {p.device} id={p.id} msg={p.msg}")
    return {"status": "ok", "received": p.model_dump()}


@app.post("/voice")
async def voice_lesson(
    file: UploadFile = File(...),
    provider: str = Query("openai", description="LLM provider after transcription"),
    include_tool_xml: bool = Query(
        False, description="Generate optical-tool XML documents from step visuals"
    ),
    include_visualization_xml: bool = Query(
        False, description="Generate visualization program XML from lesson steps"
    ),
):
    """Upload audio; transcribe with Whisper; generate lesson and persist to MongoDB."""
    if provider not in ("openai", "anthropic"):
        raise HTTPException(
            status_code=400, detail="provider must be openai or anthropic"
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty audio file")

    transcript = _transcribe_whisper(raw, file.filename)

    result = await _run_lesson_from_query(
        transcript,
        provider=provider,
        persist_mongo=True,
        include_tool_xml=include_tool_xml,
        include_visualization_xml=include_visualization_xml,
    )
    result["transcript"] = transcript
    return result


@app.post("/lesson/text")
async def lesson_from_text(body: LessonTextBody):
    """Same as /voice but with a text prompt (no Whisper). Optional on-device STT path."""
    result = await _run_lesson_from_query(
        body.query.strip(),
        provider=body.provider,
        persist_mongo=True,
    )
    result["transcript"] = body.query.strip()
    return result


@app.post("/lesson/text/xml")
async def lesson_from_text_with_xml(body: LessonTextBody):
    """Generate lesson from text with full XML output (tool_xml + visualization_xml)."""
    result = await _run_lesson_from_query(
        body.query.strip(),
        provider=body.provider,
        persist_mongo=True,
        include_tool_xml=True,
        include_visualization_xml=True,
    )
    result["transcript"] = body.query.strip()
    return result


if __name__ == "__main__":
    uvicorn.run("test_server:app", host="0.0.0.0", port=8000, log_level="info")
