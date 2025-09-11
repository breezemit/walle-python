# Walle

**Walle** is a GitLab-based release automation tool written in Python that generates release notes and changelogs from GitLab Merge Requests. It follows conventional commit patterns and supports automated release workflows.

## Features

- 🚀 **Automated Release Notes**: Generate release notes from GitLab Merge Requests
- 📝 **Changelog Management**: Update CHANGELOG.md files automatically
- 🏗️ **Batch Processing**: Process multiple projects concurrently
- 🎯 **Flexible Configuration**: Support for JSON config files and environment variables
- 🔗 **GitLab Integration**: Full GitLab API integration with retry logic
- 📦 **Multiple Output Modes**: Markdown-only, tag-only, or full release creation
- 🔄 **Conventional Commits**: Follows conventional commit format for categorization
- ⚡ **Concurrent Processing**: Multi-threaded processing for optimal performance

## Installation

```bash
# Install from source
pip install -e .

# Or using make
make install
```

## Quick Start

### 1. Configuration

Create a configuration file:

```bash
walle init-config
```

Example configuration (`walle.json`):

```json
{
  "gitlab_host": "https://gitlab.com",
  "gitlab_token": "your-token-here", 
  "project": "group/project-name"
}
```

### 2. Environment Variables

You can also configure using environment variables:

```bash
export WALLE_GITLAB_HOST=https://gitlab.com
export WALLE_GITLAB_TOKEN=your-token-here
export WALLE_PROJECT=group/project-name
```

### 3. Basic Usage

```bash
# Create a release with release notes
walle release -p group/project-name -r master -t v1.0.1

# Update changelog
walle changelog -p group/project-name -r master -t v1.0.1 -f CHANGELOG.md

# Generate markdown only (no tags/releases created)
walle release -p group/project-name -r master -t v1.0.1 -mo

# Process multiple projects
walle batch -c batch.json
```

## Commands

### Release Command

Create releases with automated release notes:

```bash
# Basic release
walle release -p group/project-name -r master -t v1.0.1

# Custom starting position
walle release -p group/project-name -r master -t v1.0.1 -s v1.0.0

# Markdown only (no tags/releases)
walle release -p group/project-name -r master -t v1.0.1 -mo

# Tags only (no releases)
walle release -p group/project-name -r master -t v1.0.1 -to

# Save to file
walle release -p group/project-name -r master -t v1.0.1 -mo -o release-notes.md
```

### Changelog Command

Update CHANGELOG.md files:

```bash
# Update changelog
walle changelog -p group/project-name -r master -t v1.0.1 -f CHANGELOG.md

# Custom starting position
walle changelog -p group/project-name -r master -t v1.0.1 -s v1.0.0 -f CHANGELOG.md

# Markdown only
walle changelog -p group/project-name -r master -t v1.0.1 -mo -o changelog-entry.md
```

### Batch Processing

Process multiple projects concurrently:

```bash
# Individual markdown files
walle batch -c batch.json -mo -o ./release-notes/

# Product-level merged markdown
walle batch -c batch.json -mo -mm --product-name "My Product v2.0" -o ./

# Create tags only
walle batch -c batch.json -to
```

Example batch configuration (`batch.json`):

```json
{
  "product_name": "My Product v2.0",
  "projects": [
    {
      "project": "group/frontend",
      "ref": "master", 
      "tag": "v1.0.0"
    },
    {
      "project": "group/backend",
      "ref": "main",
      "tag": "v2.0.0"
    },
    {
      "project": "group/mobile",
      "ref": "master",
      "tag": "v1.5.0"
    }
  ]
}
```

## Command Line Options

### Short Parameter Aliases

All commonly used parameters have short aliases:

- `--project` → `-p`
- `--config` → `-c` 
- `--markdown-only` → `-mo`
- `--tag-only` → `-to`
- `--merge-markdown` → `-mm`
- `--output` → `-o`
- `--tag` → `-t`
- `--ref` → `-r`
- `--since` → `-s`

### Global Options

- `--debug`: Enable debug logging
- `--gitlab-host`: GitLab host URL
- `--gitlab-token`: GitLab API token
- `--config-file`: Path to JSON configuration file

## Merge Request Format

Walle expects Merge Request titles to follow conventional commit format:

```
<type>(<scope>): <title content>
```

### Supported Types

- `feat` → "**New Features:**"
- `fix` → "**Bug Fix:**" 
- `refactor` → "**Changes:**"
- `docs` → "**Documentation:**"
- Others → "**Other:**"

### Example

```
feat(auth): Add user authentication system
fix(api): Resolve timeout issues in user service
refactor(ui): Modernize component structure
docs: Update API documentation
```

### Excluding Merge Requests

To exclude a Merge Request from release notes:

1. Add the `release-note-none` label to the MR
2. Or include this in the MR description:

```markdown
```release-note
none
```
```

## Advanced Features

### Custom Starting Position

Use `--since` to specify a custom starting point for changelog generation:

```bash
# Use specific tag
walle release -p myproject -r master -t v2.0.0 -s v1.5.0

# Use commit hash
walle release -p myproject -r master -t v2.0.0 -s abc123def456

# Use branch
walle release -p myproject -r master -t v2.0.0 -s feature-branch
```

### Product-level Release Notes

When using batch processing with `--merge-markdown`, release notes are combined by category:

```markdown
# My Product v2.0 Release Notes

**Bug Fixes:**
- **frontend**: Fix login form validation issue (!123)
- **backend**: Resolve database connection timeout (!456)  
- **mobile**: Fix crash on startup (!789)

**New Features:**
- **frontend**: Add dark mode support (!124)
- **backend**: Implement new API endpoint (!457)
- **mobile**: Add biometric authentication (!790)
```

### Configuration File Locations

Walle searches for configuration files in this order:

1. `walle.json` (current directory)
2. `.walle.json` (current directory)
3. `~/.walle.json` (home directory)
4. `~/.config/walle/config.json`
5. `/etc/walle/config.json`

## Development

### Setup

```bash
# Install dependencies
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type checking
black --check walle/
flake8 walle/
mypy walle/
```

### Testing

```bash
# Run tests
make test

# Or directly
pytest tests/
```

### Build

```bash
# Clean build artifacts
make clean

# Build package
python setup.py build
```

## GitLab Permissions

Your GitLab token requires the following permissions:

- `api`: Full API access
- `read_api`: Read API access
- `read_repository`: Read repository content
- `write_repository`: Create tags and releases

## CI/CD Integration

### GitLab CI Example

```yaml
stages:
  - release

release:
  stage: release
  image: python:3.9
  before_script:
    - pip install walle
  variables:
    WALLE_GITLAB_TOKEN: $GITLAB_TOKEN
    WALLE_GITLAB_HOST: $CI_SERVER_URL
  script:
    - walle release -p $CI_PROJECT_PATH -r $CI_COMMIT_SHA -t $CI_COMMIT_TAG
  only:
    - tags
    - /^v[0-9]+\.[0-9]+\.[0-9]+$/
```

### GitHub Actions Example

```yaml
name: Release
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install Walle
        run: pip install walle
      - name: Create Release
        env:
          WALLE_GITLAB_TOKEN: ${{ secrets.GITLAB_TOKEN }}
          WALLE_GITLAB_HOST: https://gitlab.com
        run: |
          walle release -p group/project -r ${{ github.sha }} -t ${{ github.ref_name }}
```

## Examples

### Basic Release Workflow

```bash
# 1. Create configuration
walle init-config

# 2. Edit walle.json with your settings

# 3. Create a release
walle release -p mygroup/myproject -r master -t v1.0.0

# 4. Update changelog
walle changelog -p mygroup/myproject -r master -t v1.0.0 -f CHANGELOG.md
```

### Multi-Project Release

```bash
# 1. Create batch configuration
cat > batch.json << EOF
{
  "product_name": "My Product Suite v2.0",
  "projects": [
    {"project": "mygroup/frontend", "ref": "master", "tag": "v2.0.0"},
    {"project": "mygroup/backend", "ref": "main", "tag": "v2.0.0"},
    {"project": "mygroup/mobile", "ref": "master", "tag": "v2.0.0"}
  ]
}
EOF

# 2. Process all projects with merged output
walle batch -c batch.json -mo -mm -o ./product-release-notes.md

# 3. Create tags for all projects
walle batch -c batch.json -to
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.