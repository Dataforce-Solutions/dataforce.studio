# dataforce.studio

This template should help get you started developing with Vue 3 in Vite!

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Type-Check, Compile and Minify for Production

```sh
npm run build
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```

## Project Structure
```
public (global app files)
src (main app folder)
|    assets
|    |    data (samples datasets)
|    |    img
|    |    theme (style-dictionary results)
|    |    base.css (base styles)
|    |    main.css (global styles)
|    |    null.css (styles reset)
|    components
|    |    authorization
|    |    homepage-tasks
|    |    layout (layout parts)
|    |    services (app tasks components)
|    |    |    tabular (components for classification & regression)
|    |    |    |    first-step (components for first step)
|    |    |    |    second-step (components for second step)
|    |    |    |    third-step (components for third step)
|    |    |    |    TabularWrapper.vue (wrapper for all steps)
|    |    ui (components must be without logic)
|    |    user (user data)
|    constants
|    helpers
|    hooks (custom hooks)
|    lib (independent services)
|    pages (all app pages here)
|    router (app router logic)
|    stores (global)
|    templates (templates for app pages)
|    utils
tokens (figma tokens)
style-dictionary.config.mjs (config for build css variables from tokens)
```