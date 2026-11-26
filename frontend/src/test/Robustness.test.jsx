import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { FavoritesProvider, useFavorites } from '../context/FavoritesContext';

vi.mock('../components/Navbar', () => ({ default: () => <div /> }));
vi.mock('../pages/Home', () => ({ default: () => <div /> }));

beforeEach(() => localStorage.clear());

describe('saved favourites', () => {
  const Names = () => {
    const { favorites, isFavorite } = useFavorites();
    isFavorite('x');
    return <p data-testid="names">{favorites.map((p) => p.planet_name).join(',')}</p>;
  };

  it.each([
    ['{"a":1}', ''],
    ['null', ''],
    ['not json', ''],
    ['[null, 5, {"planet_name":"TOI-700 d"}]', 'TOI-700 d'],
  ])('survives %s in local storage', (stored, expected) => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    localStorage.setItem('exosignal_favorites', stored);
    render(
      <FavoritesProvider>
        <Names />
      </FavoritesProvider>
    );
    expect(screen.getByTestId('names').textContent).toBe(expected);
  });
});

it('shows a message for an unknown address', () => {
  window.history.pushState({}, '', '/no-such-page');
  render(
    <FavoritesProvider>
      <App />
    </FavoritesProvider>
  );
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
});
