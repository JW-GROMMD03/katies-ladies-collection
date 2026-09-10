CREATE TABLE products (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  brand TEXT,
  description TEXT,
  price NUMERIC NOT NULL,
  original_price NUMERIC, -- For discounts
  type TEXT NOT NULL,
  category TEXT NOT NULL,
  color TEXT NOT NULL,
  image_url TEXT NOT NULL,
  status TEXT DEFAULT 'In Stock',
  views INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE transactions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  receipt_number TEXT UNIQUE NOT NULL,
  amount NUMERIC NOT NULL,
  phone_number TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);