import numpy as np
from pgmpy.inference import VariableElimination
import pandas as pd
def compare_multiple_networks_bootstrap_ll(df, models, n_bootstrap=50, random_state=42):
    """
    Compare multiple Bayesian networks using bootstrapped log-likelihood.

    Parameters
    ----------
    df : pd.DataFrame
        Observed dataset with categorical columns (strings or integers)
    models : list of tuples
        List of (name, BayesianNetwork) to compare. Each network must have CPDs attached.
        Example: [('MHIT', MHIT_copy), ('MHIT_latent', MHIT_latent_copy), ('Learned', learned_network)]
    n_bootstrap : int
        Number of bootstrap resamples
    random_state : int
        Random seed

    Returns
    -------
    pd.DataFrame
        Summary table with mean, std log-likelihood per model and which model is better
    """
    rng = np.random.default_rng(random_state)

    # Helper function to compute log-likelihood for one network
    def log_likelihood(model, df_sample):
        ll = 0
        inf = VariableElimination(model)
        observed_vars = [v for v in df_sample.columns if v in model.nodes()]

        for _, row in df_sample.iterrows():
            prob = 1.0
            for var in observed_vars:
                parents = list(model.get_parents(var))
                evidence = {p: row[p] for p in parents if p in observed_vars}

                q = inf.query([var], evidence=evidence, show_progress=False)
                cpd = model.get_cpds(var)

                # Map row value to CPD index
                if cpd.state_names:
                    val_idx = cpd.state_names[var].index(row[var])
                else:
                    val_idx = int(row[var])

                prob *= q.values[val_idx]

            ll += np.log(prob + 1e-12)  # small epsilon to avoid log(0)
        return ll

    # Initialize container for log-likelihoods
    logliks = {name: [] for name, _ in models}

    # Bootstrapping loop
    for i in range(n_bootstrap):
        sample_idx = rng.choice(df.index, size=len(df), replace=True)
        df_sample = df.iloc[sample_idx].reset_index(drop=True)

        for name, model in models:
            ll = log_likelihood(model, df_sample)
            logliks[name].append(ll)

    # Compute summary statistics
    rows = []
    for model_name, scores in logliks.items():
        rows.append({
            'Model': model_name,
            'Mean LogLik': np.mean(scores),
            'Std LogLik': np.std(scores)
        })

    summary_df = pd.DataFrame(rows)
    summary_df['Better Model'] = summary_df['Mean LogLik'] == summary_df['Mean LogLik'].max()

    pd.set_option('display.float_format', lambda x: f"{x:,.3f}")
    return summary_df


def get_cpd_complexity(model):
    """
    Returns:
      total_params: total number of free parameters in the network
      detail: dict with parameter count per node
    """
    total_params = 0
    detail = {}

    for cpd in model.get_cpds():
        node = cpd.variable
        node_card = cpd.variable_card

        parent_cards = [model.get_cardinality(parent) for parent in cpd.variables[1:]]
        parent_configurations = 1
        for c in parent_cards:
            parent_configurations *= c

        # Free parameters per CPD:
        params = (node_card - 1) * parent_configurations

        detail[node] = params
        total_params += params

    return total_params, detail