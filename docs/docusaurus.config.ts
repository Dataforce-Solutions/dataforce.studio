import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import dotenv from 'dotenv';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

dotenv.config();

const config: Config = {
  title: 'DataForce Studio',
  tagline: 'Build AI Solutions Faster than Ever',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: process.env.URL,
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
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/dsf.webp',
    navbar: {
      title: 'DataForce Studio',
      logo: {
        alt: 'My Site Logo',
        src: 'img/logo.png',
        href: '/getting-started',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Tutorial',
        },
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
              to: '/getting-started',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} DataForce Solutions GmbH. All rights reserved.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
    announcementBar: {
      id: 'wip_notice', 
      content: '🚧 This documentation is a work in progress and may be incomplete.',
      backgroundColor: '#fff3cd', 
      textColor: '#663c00',       
      isCloseable: true,
    },
  } satisfies Preset.ThemeConfig,

};

export default config;
