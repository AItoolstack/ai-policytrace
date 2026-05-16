# Sample Data

This folder contains synthetic demo documents for PolicyTrace.

The PDFs in `policytrace_demo_pack/` are fictional, text-based UK motor
insurance documents. They use invented names, policy numbers, vehicle
registration, insurer branding, address, and risk details. They are safe to use
in screenshots, demos, blog posts, GitHub examples, and Hugging Face Spaces.

Generated files:

- `Schedule of Insurance - Demo.pdf`
- `Certificate of Motor Insurance - Demo.pdf`
- `Statement of Fact - Demo.pdf`
- `Policy Booklet - Demo.pdf`
- `manifest.json`

To regenerate the pack from source:

```powershell
python scripts/generate_synthetic_policy_pack.py
```

Do not commit real customer PDFs, real policy documents, or local extraction
outputs to the public repository.
