import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../context/FavoritesContext', () => ({
  useFavorites: () => ({ favorites: [], removeFavorite: () => {} }),
}));

import Favorites from '../pages/Favorites';

// Found by the browser check of the engineering upgrade: the empty watchlist had no page heading.
describe('accessibility of the empty watchlist', () => {
  it('has a level-one heading', () => {
    render(
      <MemoryRouter>
        <Favorites />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { level: 1, name: 'No favorites yet' })).toBeInTheDocument();
  });
});
