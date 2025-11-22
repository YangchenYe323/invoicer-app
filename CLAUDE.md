# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered invoice extraction pipeline that processes RFC822 email messages and extracts structured invoice data using large language models.

**Core Abstraction**: Email bytes in (RFC822 format) → Structured data out

**Architecture & Design**: See [docs/design.md](docs/design.md) for the complete system architecture, deployment strategy, and data models.

**Deployment Platform**: The application is deployed on [Modal](https://modal.com). See [docs/modal-deployment.md](docs/modal-deployment.md) for Modal-specific guidelines and best practices.

**Quick Start**: See [QUICKSTART.md](QUICKSTART.md) for immediate usage instructions with the prototype.
