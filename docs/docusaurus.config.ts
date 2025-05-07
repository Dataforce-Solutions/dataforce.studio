import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'DataForce Studio',
  tagline: 'Build AI Solutions Faster than Ever',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://dev-docs.dataforce.studio',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'DataForce', // Usually your GitHub org/user name.
  projectName: 'DataForce Studio', // Usually your repo name.

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },

          // Useful options to enforce blogging best practices
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    navbar: {
      title: 'DataForce Studio',
      logo: {
        alt: 'My Site Logo',
        src: 'img/logo.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Tutorial',
        },
//         {to: '/blog', label: 'Blog', position: 'left'},
//         {
//           href: 'https://github.com/facebook/docusaurus',
//           label: 'GitHub',
//           position: 'right',
//         },
      ],
    },
    footer: {
      style: 'light',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Tutorial',
              to: '/docs/getting-started',
            },
          ],
        },
//         {
//           title: 'Community',
//           items: [
//             {
//               label: 'Stack Overflow',
//               href: 'https://stackoverflow.com/questions/tagged/docusaurus',
//             },
//             {
//               label: 'Discord',
//               href: 'https://discordapp.com/invite/docusaurus',
//             },
//             {
//               label: 'X',
//               href: 'https://x.com/docusaurus',
//             },
//           ],
//         },
//         {
//           title: 'More',
//           items: [
//             {
//               label: 'Blog',
//               to: '/blog',
//             },
//             {
//               label: 'GitHub',
//               href: 'https://github.com/facebook/docusaurus',
//             },
//           ],
//         },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} DataForce Solutions GmbH. All rights reserved.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
