

# SocraticSight: Multimodal AI Tutoring Agent

SocraticSight is a vision-enabled, real-time desktop AI agent designed to revolutionize interactive digital learning. Built for the Gemini Live Agent Challenge, this application moves beyond text-based chat, utilizing native audio streaming and dynamic screen-capture to provide contextual, low-latency tutoring.

By orchestrating the Gemini Developer API for real-time interaction alongside enterprise Google Cloud capabilities for multimodal generation and data persistence, SocraticSight delivers a seamless and highly scalable educational experience.

## 🏗️ System Architecture

*(Pro-Tip: Insert the Architecture Diagram you generated here!)*

SocraticSight operates on a decoupled architecture:

1. **Client Layer:** A lightweight Python desktop client (Tkinter) handling UI state, raw PCM audio capture (`PyAudio`), and workspace vision (`mss`).
2. **Real-Time Orchestration:** A bidirectional WebSocket connection to the Gemini Live API (`gemini-2.5-flash-native-audio-preview`) for ultra-low latency voice interaction and command routing.
3. **Cloud Backend:** Asynchronous integration with Google Cloud Platform (GCP). The client routes generative tasks to Vertex AI (Imagen 3 and Gemini 2.5 Flash) and persists session artifacts to Google Cloud Storage (GCS).

## ✨ Core Capabilities

* **Full-Duplex Voice Interaction:** Natural, interruptible conversational AI powered by native audio streaming.
* **Contextual Workspace Vision:** On-demand screen analysis allowing the agent to "see" and guide users through live desktop tasks.
* **Dynamic Visual Generation:** Automated routing to Vertex AI to generate high-fidelity educational diagrams displayed on a procedural digital whiteboard.
* **Automated Session Archiving:** Post-session transcript summarization and secure cloud storage of all generated visual and textual artifacts.

## 🛠️ Technology Stack

* **Language:** Python 3.9+
* **Core APIs:** Google GenAI SDK (Gemini Live API, Vertex AI)
* **Cloud Infrastructure:** Google Cloud Storage (GCS)
* **Audio & Vision Processing:** PyAudio, mss, Pillow
* **UI/UX:** Tkinter (Asynchronous Event Loop Integration)

## ⚙️ Installation & Configuration

### Prerequisites

* A Google Cloud Platform (GCP) account with an active project.
* [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed and configured on your local machine.

### 1. Repository Setup

Clone the repository and initialize the virtual environment:

```bash
git clone https://github.com/YOUR_USERNAME/SocraticSight.git
cd SocraticSight
python -m venv venv
venv\Scripts\activate  # On Windows

```

### 2. Dependency Installation

Install the required packages. *(Note: PyAudio may require C++ build tools or a pre-compiled wheel depending on your OS).*

```bash
pip install google-genai google-cloud-storage pyaudio mss Pillow

```

### 3. Environment & Cloud Authentication

SocraticSight utilizes Application Default Credentials (ADC) for secure, keyless authentication to Google Cloud services, alongside an API key for the Developer API.

1. **Authenticate local GCP credentials:**
```bash
gcloud auth application-default login

```


2. **Set your Gemini API Key:**
```bash
set GEMINI_API_KEY="your_developer_api_key_here"

```


3. **Configure Project Variables:**
Update `cloud_tools.py` with your specific infrastructure details:
```python
GCP_PROJECT_ID = "your-gcp-project-id"         
GCS_BUCKET_NAME = "your-gcs-bucket-name"    
LOCATION = "us-central1"

```



## 🚀 Usage

Execute the main application loop:

```bash
python main.py

```

**Interaction Guide:**

* **General Inquiry:** Speak naturally through your microphone (e.g., *"Explain quantum entanglement"*).
* **Vision Activation:** Request visual context (e.g., *"Look at my screen, why is this code failing?"*).
* **Visual Generation:** Request a diagram (e.g., *"Draw a diagram of the water cycle"*). The agent will display it on the digital whiteboard.
* **Graceful Shutdown:** Say *"Goodbye"* or *"Shut down"* to trigger the Cloud Storage archiving protocol before the application exits.


