# Comic Processor Project Guide

## Project Overview

This is a Python-based comic book processing tool designed to automate the organization and management of comic book collections. The project provides functionality for creating standardized folder structures, processing comic files, and integrating with external APIs like ComicVine for metadata retrieval.

### Key Technologies Used

- **Python 3.x**: Main programming language
- **requests**: HTTP library for API interactions
- **python-dotenv**: Environment variable management

### High-level Architecture

The project follows a modular approach where:

- `comic-processor.py` contains the core processing logic and ComicVine API integration
- Folder creation functionality is implemented to organize comics systematically
- API integration allows for metadata enrichment from ComicVine database

## Getting Started

### Prerequisites

- Python 3.6 or higher
- pip package manager

### Installation

1. Clone the repository
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

### Basic Usage

```python
# Import and use the comic processor
import comic_processor

# Create required folders (will be created in parent directory)
comic_processor.create_folders()

# Fetch comics from ComicVine API
comics = comic_processor.fetch_comics('spider-man', 10)

# Fetch volumes from ComicVine API  
volumes = comic_processor.fetch_volumes('marvel', 5)
```

### Environment Setup

To use the ComicVine API integration:

1. Get a free API key from [ComicVine API](https://comicvine.gamespot.com/api/)
2. Set it as an environment variable:

   ```bash
   export COMICVINE_API_KEY=your_api_key_here
   ```

## Project Structure

### Main Directories and Files

- `comic-processor.py`: Core processing logic and ComicVine API integration
- `README.md`: Project documentation
- `requirements.txt`: Python dependencies
- `.env.example`: Example environment variable configuration

### Key Components

- **Folder Creation System**: Creates standardized folder structure in parent directory:
  - `step0-trash`
  - `step1-convert` 
  - `step2-process`
  - `step2.1-remove_border`
  - `step2.2-remove_barcode`
  - `step2.5-cleanup`
  - `step2.5-covers`
  - `step3-completed`
  - `step4-done`

- **ComicVine API Integration**: Functions to fetch comic metadata:
  - `fetch_comics(query, limit)` - Search for comics
  - `fetch_volumes(query, limit)` - Search for volumes
  - `fetch_comic_by_id(id)` - Get specific comic details
  - `fetch_volume_by_id(id)` - Get specific volume details
  - `search_comics(query, filter_params)` - Advanced search with filtering

## Development Workflow

### Coding Standards

- Python 3.x with type hints
- Follow PEP 8 style guidelines
- Comprehensive error handling
- Clear function documentation with docstrings

### Testing Approach

The project includes example usage in the main function that demonstrates API functionality. For production use, developers should implement proper unit tests.

### Build and Deployment

This is a Python script-based tool that doesn't require compilation. Deployment involves:

1. Installing dependencies via pip
2. Setting environment variables
3. Running the script as needed

### Contribution Guidelines

- Follow existing code style and patterns
- Add comprehensive docstrings to new functions
- Include error handling for API interactions
- Test changes thoroughly before submitting

## Key Concepts

### Comic Processing Pipeline

The tool implements a multi-step processing pipeline:

1. **step0-trash**: Initial trash management
2. **step1-convert**: File conversion operations  
3. **step2-process**: Main processing steps
4. **step2.1-remove_border**: Border removal
5. **step2.2-remove_barcode**: Barcode removal
6. **step2.5-cleanup**: General cleanup
7. **step2.5-covers**: Cover handling
8. **step3-completed**: Completed processing
9. **step4-done**: Final destination

### ComicVine API Integration

The integration provides access to:

- Comic issue metadata (names, descriptions, publication dates)
- Volume information (publisher details, start years)
- Search capabilities with filtering options
- Detailed item retrieval by ID

## Common Tasks

### Setting Up Environment

```bash
# Create .env file with your API key
echo "COMICVINE_API_KEY=your_api_key_here" > .env
```

### Running the Processor

```python
# Run folder creation (creates all required directories)
import comic_processor
comic_processor.create_folders()

# Fetch and process comics
comics = comic_processor.fetch_comics('spider-man', 10)
for comic in comics:
    print(comic['name'])
```

### Using ComicVine API Functions

```python
# Search for comics
comics = comic_processor.fetch_comics('superman', 5)

# Search for volumes  
volumes = comic_processor.fetch_volumes('dc', 5)

# Get specific item by ID
comic = comic_processor.fetch_comic_by_id(12345)
```

## Troubleshooting

### API Key Issues

**Problem**: "ComicVine API key not found"
**Solution**: Set the `COMICVINE_API_KEY` environment variable or create a `.env` file with your key.

### Network Errors

**Problem**: API requests failing due to network issues
**Solution**: Check internet connectivity and ensure the ComicVine API is accessible.

### Permission Issues

**Problem**: Cannot create folders in parent directory
**Solution**: Ensure the script has write permissions to the parent directory.

### Missing Dependencies

**Problem**: ImportError when running the script
**Solution**: Install dependencies with `pip install -r requirements.txt`

## References

- [ComicVine API Documentation](https://comicvine.gamespot.com/api/)
- [Python Requests Library](https://requests.readthedocs.io/)
- [Python Dotenv Documentation](https://github.com/theskumar/python-dotenv)
- [PEP 8 Style Guide](https://pep8.org/)