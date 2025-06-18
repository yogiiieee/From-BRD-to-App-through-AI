# Next.js + Tailwind CSS Boilerplate

A clean, minimal, and production-ready boilerplate for Next.js 14 with Tailwind CSS integration.

## Features

- Next.js 14 with App Router
- Tailwind CSS 3.x with PostCSS configuration
- TypeScript support
- ESLint and Prettier configured
- Modern project structure
- Optimized for production

## Project Structure

```
next-tailwind-boilerplate/
├── app/
│   └── globals.css        # Tailwind CSS configuration
├── postcss.config.js      # PostCSS configuration
├── tailwind.config.js     # Tailwind CSS configuration
├── package.json          # Project dependencies
└── README.md            # Project documentation
```

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Tailwind CSS Setup
   - The project is configured with Tailwind CSS 3.x
   - PostCSS is configured in `postcss.config.js`
   - Tailwind CSS is configured in `tailwind.config.js`
   - Tailwind directives are set up in `app/globals.css`

## Using Tailwind CSS

1. Import Tailwind CSS in your components:
   ```jsx
   import '../app/globals.css';
   ```

2. Use Tailwind classes in your JSX:
   ```jsx
   <div className="bg-blue-500 text-white p-4">
     Your content here
   </div>
   ```

## Configuration Files

- `postcss.config.js`: Configures PostCSS with Tailwind CSS and Autoprefixer
- `tailwind.config.js`: Contains Tailwind CSS configuration options
- `app/globals.css`: Contains Tailwind CSS directives (@tailwind base, components, utilities)

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3003](http://localhost:3003) with your browser to see the result.

## Commands

- `npm run dev` - Start development server
- `npm run build` - Create a production build
- `npm start` - Start production server
- `npm run lint` - Run ESLint

## Project Structure

- `/app` - Next.js App Router pages and layouts
- `/public` - Static assets
- `/src` - Source code (optional)
- `/dist` or `.next` - Build output

## License

MIT

## Support

For issues or questions, please open an issue in the repository.
