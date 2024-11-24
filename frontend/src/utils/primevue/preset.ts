import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'

export const dPreset = definePreset(Aura, {
  primitive: {
    blue: {
      550: '#2673FD',
    },
  },
  semantic: {
    colorScheme: {
      light: {
        primary: {
          color: '{blue.550}',
          50: '{blue.50}',
          100: '{blue.100}',
          200: '{blue.200}',
          300: '{blue.300}',
          400: '{blue.400}',
          500: '{blue.500}',
          600: '{blue.600}',
          700: '{blue.700}',
          800: '{blue.800}',
          900: '{blue.900}',
          950: '{blue.950}',
          hover: {
            color: '{primary.600}',
          },
          active: {
            color: '{primary.700}',
          },
        },
        surface: {
          0: '#fff',
          50: '{slate.50}',
          100: '{slate.100}',
          200: '{slate.200}',
          300: '{slate.300}',
          400: '{slate.400}',
          500: '{slate.500}',
          600: '{slate.600}',
          700: '{slate.700}',
          800: '{slate.800}',
          900: '{slate.900}',
          950: '{neutral.950}',
        },
        formField: {
          filledBackground: '#F8FAFC',
        },
      },
      dark: {
        primary: {
          color: '{blue.900}',
          50: '{blue.50}',
          100: '{blue.100}',
          200: '{blue.200}',
          300: '{blue.300}',
          400: '{blue.400}',
          500: '{blue.500}',
          600: '{blue.600}',
          700: '{blue.700}',
          800: '{blue.800}',
          900: '{blue.900}',
          950: '{blue.950}',
          hover: {
            color: '{primary.800}',
          },
          active: {
            color: '{primary.600}',
          },
        },
        surface: {
          0: '#fff',
          50: '{zinc.50}',
          100: '{zinc.100}',
          200: '{zinc.200}',
          300: '{zinc.300}',
          400: '{zinc.400}',
          500: '{zinc.500}',
          600: '{zinc.600}',
          700: '{zinc.700}',
          800: '{zinc.800}',
          900: '{zinc.900}',
          950: '{neutral.950}',
        },
        formField: {
          filledBackground: ' #27272A',
        },
      },
    },
  },
  components: {
    button: {
      label: {
        font: { weight: 500 },
      },
      border: {
        radius: '8px',
      },
      padding: {
        x: '24px',
        y: '12px',
      },
      colorScheme: {
        light: {
          primary: {
            background: '{primary.color}',
            color: '{primary.contrast.color}',
          },
          help: {
            background: '{surface.0}',
            color: '{primary.500}',
            border: {
              color: '{surface.0}',
            },
            hover: {
              background: '{blue.50}',
              color: '{blue.550}',
              border: {
                color: '{blue.50}',
              },
            },
            active: {
              background: '{blue.50}',
              color: '{blue.550}',
              border: {
                color: '{blue.50}',
              },
            },
            focus: {
              ring: {
                color: '{blue.550}',
              },
            },
          },
          secondary: {
            background: '{blue.100}',
            color: '{surface.600}',
            border: {
              color: '{blue.100}',
            },
            hover: {
              background: '{blue.200}',
              color: '{surface.700}',
              border: {
                color: '{surface.200}',
              },
            },
            active: {
              background: '{blue.200}',
              color: '{surface.800}',
              border: {
                color: '{blue.200}',
              },
            },
            focus: {
              ring: {
                color: '{surface.600}',
              },
            },
          },
          outlined: {
            primary: {
              color: '{form.field.color}',
              border: {
                color: '{form.field.border.color}',
              },
              hover: {
                background: 'transparent',
                border: {
                  color: '{form.field.hover.border.color}',
                },
              },
            },
          },
        },
        dark: {
          primary: {
            color: '#fff',
          },
          help: {
            background: '{surface.900}',
            color: '{surface.0}',
            border: {
              color: '{surface.900}',
            },
            hover: {
              background: '{surface.800}',
              color: '{surface.0}',
              border: {
                color: '{surface.800}',
              },
            },
            active: {
              background: '{surface.900}',
              color: '{surface.0}',
              border: {
                color: '{surface.800}',
              },
            },
            focus: {
              ring: {
                color: '{surface.0}',
              },
            },
          },
          secondary: {
            background: '{surface.800}',
            color: '{surface.300}',
            border: {
              color: '{surface.800}',
            },
            hover: {
              background: '{surface.700}',
              color: '{surface.200}',
              border: {
                color: '{surface.700}',
              },
            },
            active: {
              background: '{surface.600}',
              color: '{surface.100}',
              border: {
                color: '{surface.600}',
              },
            },
            focus: {
              ring: {
                color: '{surface.300}',
              },
            },
          },
          outlined: {
            primary: {
              color: '#FFFFFF',
              border: {
                color: '#52525B',
              },
            },
          },
        },
      },
    },
    card: {
      colorScheme: {
        dark: {
          background: '#18181B',
        },
      },
    },
    inputtext: {
      filled: {
        background: '{form.field.filled.background}',
      },
    },
    message: {
      colorScheme: {
        dark: {
          error: {
            simple: {
              color: '{floatlabel.invalid.color}',
            },
          },
        },
      },
    },
  },
})
