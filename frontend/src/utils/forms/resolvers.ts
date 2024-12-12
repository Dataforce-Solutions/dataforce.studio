import { z } from 'zod'
import { zodResolver } from '@primevue/forms/resolvers/zod'

export const signInResolver = zodResolver(
  z.object({
    email: z.string().email({ message: 'Email is incorrect' }),
    password: z.string().min(8, { message: 'Minimum password length 8 characters' }),
  }),
)

export const signUpResolver = zodResolver(
  z.object({
    username: z.string().min(3, { message: 'Username is required.' }),
    email: z.string().email('Email incorrect'),
    password: z.string().min(8, { message: 'Minimum password length 8 characters' }),
  }),
)

export const forgotPasswordResolver = zodResolver(
  z.object({
    email: z.string().email({ message: 'Email is incorrect' }),
  }),
)

export const resetPasswordResolver = zodResolver(
  z
    .object({
      password: z.string().min(8, { message: 'The password must be more than 8 characters' }),
      password_confirm: z
        .string()
        .min(8, { message: 'The password must be more than 8 characters' }),
    })
    .refine((data) => data.password === data.password_confirm, {
      message: 'Passwords must match',
      path: ['password_confirm'],
    }),
)

export const userSettingResolver = zodResolver(
  z.object({
    username: z.string().min(3, { message: 'Name must be more 3 characters' }),
    email: z.string().email({ message: 'Email is incorrect' }),
  }),
)

export const userChangePasswordResolver = zodResolver(
  z
    .object({
      current_password: z
        .string()
        .min(8, { message: 'The password must be more than 8 characters' }),
      new_password: z.string().min(8, { message: 'The password must be more than 8 characters' }),
      confirmPassword: z
        .string()
        .min(8, { message: 'The password must be more than 8 characters' }),
    })
    .refine((data) => data.new_password === data.confirmPassword, {
      message: 'Passwords must match',
      path: ['confirmPassword'],
    }),
)
