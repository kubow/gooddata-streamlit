import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from math import pi

# Set the variables you want to plot

# Define the number of variables you want to plot (in this case, 5)

# Create a function to plot the radar chart
def radar_chart(data: pd.DataFrame):
    variables = list(data.columns[1:])
    num_vars = len(variables)
    # Set the angles for each variable
    angles = [n / float(num_vars) * 2 * pi for n in range(num_vars)]
    angles += angles[:1]
    
    # Create the subplots
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    # Plot each group on the radar chart
    for i, group in enumerate(data['group']):
        values = data.loc[i, variables].values.flatten().tolist()
        values += values[:1]
        ax.plot(angles, values, linewidth=2, linestyle='solid', label=group)
        ax.fill(angles, values, alpha=0.25)
    
    # Set the labels for the chart
    ax.set_thetagrids([a * 180 / pi for a in angles[:-1]], variables)
    ax.set_title('Radar Chart', fontsize=20, y=1.05)
    ax.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    
    # Show the chart
    st.pyplot(fig)
