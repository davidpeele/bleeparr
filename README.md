# Bleeparr 2.0

Bleeparr 2.0 is a profanity-cleaning tool for TV shows and movies that integrates with Sonarr and Radarr media management systems. The application automatically detects and censors profanity in videos by muting bad words based on subtitles and AI speech recognition.

## Features

- **Modern Web Interface**: Clean, responsive UI built with React
- **Sonarr Integration**: Connect to your Sonarr instance to process TV shows
- **Radarr Integration**: Connect to your Radarr instance to process movies (optional)
- **Automatic Processing**: Monitor Sonarr/Radarr for new downloads and process them automatically
- **Manual Processing**: Manually trigger processing for specific episodes or entire series
- **Smart Profanity Detection**: Uses multi-layered detection strategy:
  - Subtitle scanning for obvious profanity
  - Whisper AI transcription (small + medium fallback) for audio verification
  - Final fallback to mute entire subtitle segments if needed
- **Configurable Settings**: Adjust detection sensitivity, output formats, and more
- **Dashboard**: View processing statistics, queue status, and system health
- **Dockerized**: Easy deployment with Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Sonarr and/or Radarr setup with API access
- A list of words to censor in `swears.txt`

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/davidpeele/bleeparr.git
   cd bleeparr
   ```

2. Create or modify the `swears.txt` file with the words you want to censor, one per line.
   Prepare the swears.txt file:
   ```bash
   # Copy the example file to create your own swears.txt
   cp swears.default.txt swears.txt
   
   # Optionally edit the file to customize the list of words to censor
   nano swears.txt

3. Edit the `docker-compose.yml` file to set your Sonarr/Radarr URLs and API keys.


4. Start the application:
   ```bash
   docker compose up -d
   ```

5. Access the web interface at [http://localhost:5050](http://localhost:5050)

## Configuration

### Environment Variables

You can configure Bleeparr by editing the environment variables in `docker-compose.yml`:

- `SONARR_URL`: URL to your Sonarr instance (e.g., http://localhost:8989)
- `SONARR_API_KEY`: Your Sonarr API key
- `RADARR_URL`: URL to your Radarr instance (optional)
- `RADARR_API_KEY`: Your Radarr API key (optional)
- `SWEARS_FILE`: Path to your swear words file
- `OUTPUT_PREFIX`: Prefix for cleaned files (default: "clean_")
- `OUTPUT_DIRECTORY`: Directory for cleaned files (default: same as input)
- `ENABLE_AUTO_PROCESSING`: Set to 1 to enable automatic processing
- `POLL_INTERVAL_SECONDS`: How often to check for new downloads (default: 300)
- `BOOST_DB`: Audio boost level in dB for improved detection (default: 6)
- `PRE_BUFFER`: Pre-mute buffer in milliseconds (default: 100)
- `POST_BUFFER`: Post-mute buffer in milliseconds (default: 100)
- `BLEEPTOOL`: Passes to run - options: S-M-FSM, S-FSM, S-M, S (default: S-M-FSM)

### Web Interface

The web interface allows you to:

1. **Dashboard**: View system status, processing statistics, and recent activities
2. **TV Shows**: Manage which shows are filtered and manually trigger processing
3. **Settings**: Configure Sonarr/Radarr connections and profanity cleaning options

## Development

### Project Structure

- `backend/`: FastAPI backend
  - `api/`: API routes and core functionality
  - `db.py`: Database management
  - `tasks.py`: Background tasks and polling
- `frontend/`: React frontend
  - `src/components/`: React components 
  - `src/assets/`: Static assets
- `bleeparr-1.1.py`: Core profanity cleaning engine
- `Dockerfile`: Container definition
- `docker-compose.yml`: Container orchestration

### Running for Development

For development, you can run the frontend and backend separately:

#### Backend

```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 5050
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Troubleshooting

- **Database Issues**: If the database becomes corrupted, you can delete the `data/bleeparr.db` file and restart the application.
- **Connection Problems**: Ensure your Sonarr/Radarr URLs and API keys are correct.
- **Processing Failures**: Check that the `swears.txt` file exists and contains valid entries.
- **Container Access**: If using network_mode: host, ensure that the ports are not already in use.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open-source and available under the MIT License.

## Credits

Bleeparr uses:
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)
- [Subliminal](https://github.com/Diaoul/subliminal)
- [FFmpeg](https://ffmpeg.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)
