# ASK Card Generator

Generates print-ready A4 PDFs of picture cards for AAC/ASK (alternativ og supplerende kommunikasjon). Place your images in a session folder, run the script, and get a PDF ready to print, laminate, and cut.

Each card shows the image with the filename as the label — `stor_bror.jpg` becomes a card labelled **stor bror**.

## Usage

```bash
./make_cards.sh sessions/2026-03-familie
```

The PDF is saved to `output/2026-03-familie.pdf`.

Run without arguments to see help:

```bash
./make_cards.sh
```

## Setup

```bash
sudo pacman -S python-pillow python-reportlab
```

## Session folders

Organize images under `sessions/`, one folder per session:

```
sessions/
├── 2026-03-familie/
│   ├── mamma.jpg
│   ├── pappa.png
│   └── stor_bror.webp
└── 2026-04-skole/
    └── ...
```

- Supported formats: `jpg`, `jpeg`, `png`, `webp`, `avif`
- Filename stem (without extension) becomes the card label
- Underscores in filenames are replaced with spaces
- Cards are sorted alphabetically within each session

## Output

- A4 page, 3 columns × 4 rows = 12 cards per page
- Cards are square with a border, label at top, image below
- PDF is saved to `output/<session-name>.pdf`
