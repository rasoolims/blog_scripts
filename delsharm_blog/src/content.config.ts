import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// 1. Schema for your Markdown blog posts
const blogCollection = defineCollection({
  // Tells Astro to look for Markdown files in the blog folder
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string().default('—'),
    // Astro automatically parses standard YYYY-MM-DD dates into Date objects
    date: z.date().or(z.string()), 
    jalaliDate: z.string().optional(),
    tags: z.array(z.string()).default([]),
    pinned: z.boolean().optional(),
  }),
});

// 2. Schema for your JSON and YAML comment files
const commentsCollection = defineCollection({
  // Tells Astro to look for both JSON and YAML files in the comments folder
  loader: glob({ pattern: '**/*.{json,yml,yaml}', base: './src/content/comments' }),
  schema: z.object({
    postSlug: z.string(),
    name: z.string(),
    email: z.string().optional(),
    url: z.string().optional(),
    // z.coerce.date() safely converts both JSON strings and YAML Date objects!
    date: z.coerce.date(),
    message: z.string(),
    // Optional response block for when you want to reply
    adminResponse: z.object({
      date: z.coerce.date(),
      message: z.string()
    }).nullable().optional()
  }),
});

// 3. Export all collections so Astro can use them globally
export const collections = {
  'blog': blogCollection,
  'comments': commentsCollection,
};